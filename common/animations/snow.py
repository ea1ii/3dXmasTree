import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class SnowAnimation(Animation):
    name = "snow"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Random-sized white snow blobs fall through the 3D LED layout."

    BLOB_DENSITY_PER_LED = 18
    MAX_BLOBS = 20
    BLOB_SPACING_RANGE = (0.65, 1.5)
    BLOB_HEIGHT_RANGE = (0.008, 0.12)
    FALL_SPEED_RANGE = (0.12, 0.35)

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
        self.blob_count = min(
            self.MAX_BLOBS,
            max(1, round(led_count / self.BLOB_DENSITY_PER_LED)),
        )
        self.blobs = [self._new_blob(initial=True) for _ in range(self.blob_count)]
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
        return SnowAnimation._fallback_positions(led_count)

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
        if not positive_distances:
            return self.height / 10
        return sum(positive_distances) / len(positive_distances)

    def _new_blob(self, initial=False):
        anchor = self.generator.choice(self.positions)
        minimum_radius = min(
            self.led_spacing * self.BLOB_SPACING_RANGE[0],
            self.height * self.BLOB_HEIGHT_RANGE[1],
        )
        maximum_radius = max(
            minimum_radius,
            min(
                self.led_spacing * self.BLOB_SPACING_RANGE[1],
                self.height * self.BLOB_HEIGHT_RANGE[1],
            ),
        )
        radius = self.generator.uniform(minimum_radius, maximum_radius)
        z = (
            self.generator.uniform(self.minimum_z, self.maximum_z + radius)
            if initial
            else self.maximum_z + radius
        )
        return {
            "x": anchor[0],
            "y": anchor[1],
            "z": z,
            "radius": radius,
            "speed": self.height * self.generator.uniform(*self.FALL_SPEED_RANGE),
        }

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        brightness = [0.0] * self.led_count
        for blob_index, blob in enumerate(self.blobs):
            blob["z"] -= blob["speed"] * delta_seconds
            if blob["z"] < self.minimum_z - blob["radius"]:
                self.blobs[blob_index] = blob = self._new_blob()

            for led_index, position in enumerate(self.positions):
                distance_squared = sum(
                    (position[axis] - blob[axis_name]) ** 2
                    for axis, axis_name in enumerate(("x", "y", "z"))
                )
                distance = math.sqrt(distance_squared)
                if distance < blob["radius"]:
                    brightness[led_index] = max(
                        brightness[led_index],
                        1.0 - distance / blob["radius"],
                    )

        return [
            (channel, channel, channel)
            for channel in (round(level * 255) for level in brightness)
        ]

    def stop(self) -> None:
        self.running = False
        self.blobs.clear()