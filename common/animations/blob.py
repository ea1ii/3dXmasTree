import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class BlobAnimation(Animation):
    name = "blob"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A hue-shifting sphere bounces and changes size inside the tree."

    SPEED_RANGE = (0.2, 0.65)
    SIZE_CHANGE_RANGE = (1.5, 4.0)
    HUE_CHANGE_RANGE = (3.0, 8.0)

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
        self.base_radius = self._estimate_base_radius()
        self.minimum_radius = min(self.led_spacing * 0.75, self.height * 0.08)
        self.maximum_radius = max(
            self.minimum_radius,
            min(self.led_spacing * 3.0, self.height * 0.16, self.base_radius * 0.3),
        )
        self.radius = self._random_radius()
        self.position = self._random_interior_position()
        self.velocity = self._random_velocity()
        self.size_start = self.radius
        self.size_target = self._random_radius()
        self.size_elapsed = 0.0
        self.size_duration = self.generator.uniform(*self.SIZE_CHANGE_RANGE)
        self.current_hue = self.generator.random()
        self.target_hue = self.generator.random()
        self.hue_elapsed = 0.0
        self.hue_duration = self.generator.uniform(*self.HUE_CHANGE_RANGE)
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
        return BlobAnimation._fallback_positions(led_count)

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

    def _estimate_base_radius(self):
        estimates = []
        for x, y, z in self.positions:
            height_fraction = (z - self.minimum_z) / self.height
            remaining_cone = max(0.15, 1.0 - height_fraction)
            estimates.append(math.hypot(x, y) / remaining_cone)
        estimate = max(estimates, default=self.height * 0.34)
        return max(estimate * 1.1, self.height * 0.1)

    def _random_radius(self):
        return self.generator.uniform(self.minimum_radius, self.maximum_radius)

    def _random_velocity(self):
        while True:
            direction = [self.generator.uniform(-1.0, 1.0) for _ in range(3)]
            length = math.sqrt(sum(component * component for component in direction))
            if length > 0:
                break
        speed = self.height * self.generator.uniform(*self.SPEED_RANGE)
        return [component / length * speed for component in direction]

    def _radial_limit(self, z):
        height_fraction = min(1.0, max(0.0, (z - self.minimum_z) / self.height))
        return max(0.0, self.base_radius * (1.0 - height_fraction) - self.radius)

    def _random_interior_position(self):
        minimum_z = self.minimum_z + self.radius
        maximum_z = self.maximum_z - self.radius
        z = self.generator.uniform(minimum_z, max(minimum_z, maximum_z))
        maximum_radius = self._radial_limit(z)
        radial_distance = maximum_radius * math.sqrt(self.generator.random())
        angle = self.generator.uniform(0.0, 2 * math.pi)
        return [radial_distance * math.cos(angle), radial_distance * math.sin(angle), z]

    @staticmethod
    def _smoothstep(progress):
        progress = min(1.0, max(0.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _update_size(self, delta_seconds):
        self.size_elapsed += delta_seconds
        if self.size_elapsed >= self.size_duration:
            self.size_start = self.size_target
            self.size_target = self._random_radius()
            self.size_elapsed = 0.0
            self.size_duration = self.generator.uniform(*self.SIZE_CHANGE_RANGE)
        progress = self._smoothstep(self.size_elapsed / self.size_duration)
        self.radius = self.size_start + (self.size_target - self.size_start) * progress

    def _update_hue(self, delta_seconds):
        self.hue_elapsed += delta_seconds
        if self.hue_elapsed >= self.hue_duration:
            self.current_hue = self.target_hue
            self.target_hue = self.generator.random()
            self.hue_elapsed = 0.0
            self.hue_duration = self.generator.uniform(*self.HUE_CHANGE_RANGE)
        progress = self._smoothstep(self.hue_elapsed / self.hue_duration)
        hue_delta = (self.target_hue - self.current_hue + 0.5) % 1.0 - 0.5
        return (self.current_hue + hue_delta * progress) % 1.0

    def _move_and_bounce(self, delta_seconds):
        for axis in range(3):
            self.position[axis] += self.velocity[axis] * delta_seconds

        minimum_z = self.minimum_z + self.radius
        maximum_z = self.maximum_z - self.radius
        if self.position[2] < minimum_z:
            self.position[2] = minimum_z
            self.velocity[2] = abs(self.velocity[2])
        elif self.position[2] > maximum_z:
            self.position[2] = maximum_z
            self.velocity[2] = -abs(self.velocity[2])

        radial_limit = self._radial_limit(self.position[2])
        radial_distance = math.hypot(self.position[0], self.position[1])
        if radial_distance > radial_limit:
            if radial_distance > 0:
                normal_x = self.position[0] / radial_distance
                normal_y = self.position[1] / radial_distance
                self.position[0] = normal_x * radial_limit
                self.position[1] = normal_y * radial_limit
                outward_speed = self.velocity[0] * normal_x + self.velocity[1] * normal_y
                if outward_speed > 0:
                    self.velocity[0] -= 2 * outward_speed * normal_x
                    self.velocity[1] -= 2 * outward_speed * normal_y
                    tangent_kick = self.generator.uniform(-0.2, 0.2) * self.height
                    self.velocity[0] -= normal_y * tangent_kick
                    self.velocity[1] += normal_x * tangent_kick

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._update_size(delta_seconds)
        hue = self._update_hue(delta_seconds)
        self._move_and_bounce(delta_seconds)
        color = tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, 0.9, 1.0)
        )
        frame = []
        for x, y, z in self.positions:
            distance = math.sqrt(
                (x - self.position[0]) ** 2
                + (y - self.position[1]) ** 2
                + (z - self.position[2]) ** 2
            )
            intensity = max(0.0, 1.0 - distance / self.radius)
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame

    def stop(self) -> None:
        self.running = False