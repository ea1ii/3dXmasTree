import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class LaserAnimation(Animation):
    name = "laser"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A bright 3D beam rotates around the tree and cycles through vivid hues."

    SABER_COLORS = (
        (20, 90, 255),
        (20, 255, 90),
        (255, 28, 12),
        (180, 35, 255),
    )
    ELEVATION_RANGE = (-0.55, 0.55)
    ANGULAR_SPEED_RANGE = (2.0, 4.5)
    DIRECTION_CHANGE_RANGE = (1.0, 3.0)
    ORIGIN_DRIFT_RANGE = (6.0, 12.0)
    COLOR_CYCLE_RANGE = (1.5, 2.5)

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
        self.tree_radius = max(
            math.hypot(position[0], position[1]) for position in self.positions
        )
        origin_y_limit = self.tree_radius * 0.6
        origin_y = self.generator.uniform(-origin_y_limit, origin_y_limit)
        self.origin = [
            0.0,
            origin_y,
            self.generator.uniform(
                self.minimum_z + self.height * 0.1,
                self.maximum_z - self.height * 0.1,
            ),
        ]
        self.origin_target_y = self.generator.uniform(-origin_y_limit, origin_y_limit)
        self.origin_drift_remaining = self.generator.uniform(*self.ORIGIN_DRIFT_RANGE)
        self.origin_y_speed = (
            (self.origin_target_y - origin_y) / self.origin_drift_remaining
        )
        self.beam_length = max(self.tree_radius * 2.2, self.height * 0.35)
        self.beam_radius = max(self.led_spacing * 2.0, self.height * 0.02)
        self.azimuth = self.generator.uniform(0.0, 2 * math.pi)
        self.angular_speed = self._random_angular_speed()
        self.direction_change_remaining = self.generator.uniform(*self.DIRECTION_CHANGE_RANGE)
        self.elevation = self.generator.uniform(*self.ELEVATION_RANGE)
        self.target_elevation = self.generator.uniform(*self.ELEVATION_RANGE)
        self.elevation_speed = self.generator.uniform(0.15, 0.55)
        self.color_phase = self.generator.random() * len(self.SABER_COLORS)
        self.color_speed = 1.0 / self.generator.uniform(*self.COLOR_CYCLE_RANGE)
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
        return LaserAnimation._fallback_positions(led_count)

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

    def _random_angular_speed(self):
        direction = self.generator.choice((-1.0, 1.0))
        return direction * self.generator.uniform(*self.ANGULAR_SPEED_RANGE)

    @staticmethod
    def _smoothstep(progress):
        progress = min(1.0, max(0.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _beam_color(self):
        self.color_phase = (self.color_phase + self.color_speed) % len(self.SABER_COLORS)
        index = int(self.color_phase)
        progress = self._smoothstep(self.color_phase - index)
        first = self.SABER_COLORS[index]
        second = self.SABER_COLORS[(index + 1) % len(self.SABER_COLORS)]
        return tuple(
            round(start + (end - start) * progress)
            for start, end in zip(first, second)
        )

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.origin_drift_remaining -= delta_seconds
        self.origin[1] += self.origin_y_speed * delta_seconds
        if self.origin_drift_remaining <= 0:
            self.origin[1] = self.origin_target_y
            origin_y_limit = self.tree_radius * 0.6
            self.origin_target_y = self.generator.uniform(-origin_y_limit, origin_y_limit)
            self.origin_drift_remaining = self.generator.uniform(*self.ORIGIN_DRIFT_RANGE)
            self.origin_y_speed = (
                (self.origin_target_y - self.origin[1]) / self.origin_drift_remaining
            )

        self.direction_change_remaining -= delta_seconds
        if self.direction_change_remaining <= 0:
            self.angular_speed = self._random_angular_speed()
            self.target_elevation = self.generator.uniform(*self.ELEVATION_RANGE)
            self.elevation_speed = self.generator.uniform(0.15, 0.55)
            self.direction_change_remaining = self.generator.uniform(*self.DIRECTION_CHANGE_RANGE)

        self.azimuth = (self.azimuth + self.angular_speed * delta_seconds) % (2 * math.pi)
        elevation_delta = self.target_elevation - self.elevation
        elevation_step = self.elevation_speed * delta_seconds
        if abs(elevation_delta) <= elevation_step:
            self.elevation = self.target_elevation
        else:
            self.elevation += math.copysign(elevation_step, elevation_delta)

        horizontal = math.cos(self.elevation)
        direction = (
            horizontal * math.cos(self.azimuth),
            horizontal * math.sin(self.azimuth),
            math.sin(self.elevation),
        )
        color = self._beam_color()
        frame = []
        for position in self.positions:
            offset = tuple(position[axis] - self.origin[axis] for axis in range(3))
            along_beam = sum(offset[axis] * direction[axis] for axis in range(3))
            if 0 <= along_beam <= self.beam_length:
                distance_squared = sum(component * component for component in offset)
                radial_distance = math.sqrt(max(0.0, distance_squared - along_beam * along_beam))
                intensity = max(0.0, 1.0 - radial_distance / self.beam_radius)
            else:
                intensity = 0.0
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame

    def stop(self) -> None:
        self.running = False