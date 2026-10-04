import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class MeteorsAnimation(Animation):
    name = "meteors"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Random 3D meteors fall through the tree with fading colored trails."

    SPAWN_INTERVAL_RANGE = (0.15, 1.4)
    FALL_SPEED_RANGE = (0.45, 1.2)
    TILT_ANGLE_RANGE = (0.0, math.radians(58))
    BLOB_RADIUS_SPACING_RANGE = (0.55, 1.1)
    TRAIL_LENGTH_SPACING_RANGE = (2.0, 8.0)
    MAX_BLOBS = 12
    COLOR_STOPS = (
        (255, 78, 5),
        (255, 177, 64),
        (218, 242, 255),
        (42, 112, 255),
    )

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.generator = random.Random()
        self.positions = self._read_positions(parameters.get("positions"), led_count)
        self.minimum_z = min(position[2] for position in self.positions)
        self.maximum_z = max(position[2] for position in self.positions)
        self.height = self.maximum_z - self.minimum_z
        if self.height <= 0:
            self.height = 1.0
            self.maximum_z = self.minimum_z + self.height
        self.led_spacing = self._estimate_led_spacing()
        self.base_radius = max(
            math.hypot(position[0], position[1]) for position in self.positions
        )
        self.meteors = []
        self.spawn_remaining = 0.0
        self.running = True

    @staticmethod
    def _read_positions(raw_positions, led_count):
        if isinstance(raw_positions, Sequence) and len(raw_positions) == led_count:
            try:
                positions = [
                    tuple(float(coordinate) for coordinate in position)
                    for position in raw_positions
                ]
                if all(
                    len(position) == 3
                    and all(math.isfinite(value) for value in position)
                    for position in positions
                ):
                    return positions
            except (TypeError, ValueError):
                pass
        return MeteorsAnimation._fallback_positions(led_count)

    @staticmethod
    def _fallback_positions(led_count):
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    def _estimate_led_spacing(self):
        if len(self.positions) < 2:
            return self.height / 10
        distances = [
            math.sqrt(sum((first[axis] - second[axis]) ** 2 for axis in range(3)))
            for first, second in zip(self.positions, self.positions[1:])
        ]
        positive_distances = [distance for distance in distances if distance > 0]
        return sum(positive_distances) / len(positive_distances) if positive_distances else self.height / 10

    def _random_color(self):
        position = self.generator.random() * (len(self.COLOR_STOPS) - 1)
        stop_index = min(int(position), len(self.COLOR_STOPS) - 2)
        amount = position - stop_index
        first = self.COLOR_STOPS[stop_index]
        second = self.COLOR_STOPS[stop_index + 1]
        return tuple(
            round(start + (end - start) * amount)
            for start, end in zip(first, second)
        )

    def _new_meteor(self):
        tilt = self.generator.uniform(*self.TILT_ANGLE_RANGE)
        azimuth = self.generator.uniform(0.0, 2 * math.pi)
        fall_speed = self.height * self.generator.uniform(*self.FALL_SPEED_RANGE)
        horizontal_speed = fall_speed * math.sin(tilt)
        velocity = (
            horizontal_speed * math.cos(azimuth),
            horizontal_speed * math.sin(azimuth),
            -fall_speed * math.cos(tilt),
        )
        start_radius = self.generator.uniform(0.0, self.base_radius * 0.8)
        start_angle = self.generator.uniform(0.0, 2 * math.pi)
        minimum_blob_radius = self.led_spacing * self.BLOB_RADIUS_SPACING_RANGE[0]
        maximum_blob_radius = max(
            minimum_blob_radius,
            min(
                self.led_spacing * self.BLOB_RADIUS_SPACING_RANGE[1],
                self.height * 0.1,
            ),
        )
        blob_radius = self.generator.uniform(minimum_blob_radius, maximum_blob_radius)
        trail_length = min(
            self.led_spacing * self.generator.uniform(*self.TRAIL_LENGTH_SPACING_RANGE),
            self.height * 0.6,
        )
        return {
            "position": [
                start_radius * math.cos(start_angle),
                start_radius * math.sin(start_angle),
                self.maximum_z + blob_radius,
            ],
            "velocity": velocity,
            "direction": tuple(component / fall_speed for component in velocity),
            "radius": blob_radius,
            "trail_length": max(self.led_spacing, trail_length),
            "color": self._random_color(),
        }

    def _advance_meteors(self, delta_seconds):
        self.spawn_remaining -= delta_seconds
        while self.spawn_remaining <= 0:
            if len(self.meteors) < self.MAX_BLOBS:
                self.meteors.append(self._new_meteor())
            self.spawn_remaining += self.generator.uniform(*self.SPAWN_INTERVAL_RANGE)

        active_meteors = []
        for meteor in self.meteors:
            position = meteor["position"]
            velocity = meteor["velocity"]
            for axis in range(3):
                position[axis] += velocity[axis] * delta_seconds
            if position[2] >= self.minimum_z - meteor["trail_length"]:
                active_meteors.append(meteor)
        self.meteors = active_meteors

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_meteors(delta_seconds)
        brightness = [0.0] * self.led_count
        colors = [(0, 0, 0)] * self.led_count
        for meteor in self.meteors:
            head = meteor["position"]
            direction = meteor["direction"]
            radius = meteor["radius"]
            trail_length = meteor["trail_length"]
            for led_index, position in enumerate(self.positions):
                offset = tuple(position[axis] - head[axis] for axis in range(3))
                behind = -sum(offset[axis] * direction[axis] for axis in range(3))
                distance_squared = sum(component * component for component in offset)
                if behind < 0:
                    distance = math.sqrt(distance_squared)
                    intensity = max(0.0, 1.0 - distance / radius)
                elif behind <= trail_length:
                    radial_distance = math.sqrt(max(0.0, distance_squared - behind * behind))
                    radial_intensity = max(0.0, 1.0 - radial_distance / radius)
                    trail_fade = (1.0 - behind / trail_length) ** 1.6
                    intensity = radial_intensity * trail_fade
                else:
                    intensity = 0.0

                if intensity > brightness[led_index]:
                    brightness[led_index] = intensity
                    colors[led_index] = meteor["color"]

        return [
            tuple(round(channel * level) for channel in color)
            for color, level in zip(colors, brightness)
        ]

    def stop(self) -> None:
        self.running = False
        self.meteors.clear()