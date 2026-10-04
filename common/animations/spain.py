import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class SpainAnimation(Animation):
    name = "spain"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A thick Spanish flag rotates randomly at the center of the tree."

    RED = (255, 0, 0)
    YELLOW = (255, 204, 0)
    ANGULAR_SPEED_RANGE = (0.2, 1.2)
    SPEED_CHANGE_RANGE = (0.5, 2.0)

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
        self.center = (0.0, 0.0, (self.minimum_z + self.maximum_z) / 2)
        self.led_spacing = self._estimate_led_spacing()
        tree_radius = max(
            math.hypot(position[0] - self.center[0], position[1] - self.center[1])
            for position in self.positions
        )
        self.flag_width = max(tree_radius * 2.1, self.led_spacing * 3.0)
        self.flag_height = max(self.height * 1.05, self.led_spacing * 3.0)
        self.flag_thickness = max(self.led_spacing * 2.2, self.height * 0.025)
        self.angles = [self.generator.uniform(-math.pi, math.pi) for _ in range(3)]
        self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
        self.speed_change_remaining = self.generator.uniform(*self.SPEED_CHANGE_RANGE)
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
        sign = self.generator.choice((-1.0, 1.0))
        return sign * self.generator.uniform(*self.ANGULAR_SPEED_RANGE)

    @staticmethod
    def _world_to_flag(position, center, angles):
        x = position[0] - center[0]
        y = position[1] - center[1]
        z = position[2] - center[2]

        cosine = math.cos(angles[0])
        sine = math.sin(angles[0])
        y, z = cosine * y + sine * z, -sine * y + cosine * z

        cosine = math.cos(angles[1])
        sine = math.sin(angles[1])
        x, z = cosine * x - sine * z, sine * x + cosine * z

        cosine = math.cos(angles[2])
        sine = math.sin(angles[2])
        x, y = cosine * x + sine * y, -sine * x + cosine * y
        return x, y, z

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.speed_change_remaining -= delta_seconds
        if self.speed_change_remaining <= 0:
            self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
            self.speed_change_remaining = self.generator.uniform(*self.SPEED_CHANGE_RANGE)
        for axis in range(3):
            self.angles[axis] = (
                self.angles[axis] + self.angular_speeds[axis] * delta_seconds
            ) % (2 * math.pi)

        frame = [(0, 0, 0)] * self.led_count
        flag_leds = []
        for index, position in enumerate(self.positions):
            local_x, local_y, local_z = self._world_to_flag(
                position,
                self.center,
                self.angles,
            )
            if (
                abs(local_x) <= self.flag_width / 2
                and abs(local_y) <= self.flag_thickness / 2
                and abs(local_z) <= self.flag_height / 2
            ):
                flag_leds.append((index, local_z))

        flag_leds.sort(key=lambda item: item[1])
        red_per_edge = min(
            len(flag_leds) // 2,
            max(1, round(len(flag_leds) / 3)),
        )
        for rank, (index, _local_z) in enumerate(flag_leds):
            if rank < red_per_edge or rank >= len(flag_leds) - red_per_edge:
                frame[index] = self.RED
            else:
                frame[index] = self.YELLOW
        return frame

    def stop(self) -> None:
        self.running = False