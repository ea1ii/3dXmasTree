import colorsys
import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class SingleSliceAnimation(Animation):
    name = "single_slice"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A thick, hue-shifting 3D slice moves and rotates through the tree."

    SLAB_HEIGHT_FRACTION = 0.08
    TRANSLATION_DURATION_RANGE = (2.5, 7.0)
    ANGULAR_SPEED_RANGE = (0.25, 1.5)
    ROTATION_CHANGE_RANGE = (0.4, 1.5)
    HUE_CHANGE_RANGE = (2.0, 6.0)

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
        self.thickness = min(
            self.height * 0.4,
            max(self.height * self.SLAB_HEIGHT_FRACTION, self.led_spacing * 2.5),
        )

        self.angles = [self.generator.uniform(-math.pi, math.pi) for _ in range(3)]
        self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
        self.rotation_change_remaining = self.generator.uniform(*self.ROTATION_CHANGE_RANGE)
        self.offset_fraction = self.generator.uniform(0.0, 1.0)
        self.move_direction = self.generator.choice((-1.0, 1.0))
        self.translation_duration = self.generator.uniform(*self.TRANSLATION_DURATION_RANGE)
        self.hue = self.generator.random()
        self.target_hue = self.generator.random()
        self.hue_elapsed = 0.0
        self.hue_duration = self.generator.uniform(*self.HUE_CHANGE_RANGE)
        self.running = True

    def _random_angular_speed(self):
        sign = self.generator.choice((-1.0, 1.0))
        return sign * self.generator.uniform(*self.ANGULAR_SPEED_RANGE)

    def _normal(self):
        x, y, z = 0.0, 0.0, 1.0
        cosine = math.cos(self.angles[0])
        sine = math.sin(self.angles[0])
        y, z = y * cosine - z * sine, y * sine + z * cosine

        cosine = math.cos(self.angles[1])
        sine = math.sin(self.angles[1])
        x, z = x * cosine + z * sine, -x * sine + z * cosine

        cosine = math.cos(self.angles[2])
        sine = math.sin(self.angles[2])
        x, y = x * cosine - y * sine, x * sine + y * cosine

        magnitude = math.sqrt(x * x + y * y + z * z)
        return x / magnitude, y / magnitude, z / magnitude

    @staticmethod
    def _smoothstep(progress):
        progress = min(1.0, max(0.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _advance_hue(self, delta_seconds):
        self.hue_elapsed += delta_seconds
        if self.hue_elapsed >= self.hue_duration:
            self.hue = self.target_hue
            self.target_hue = self.generator.random()
            self.hue_elapsed = 0.0
            self.hue_duration = self.generator.uniform(*self.HUE_CHANGE_RANGE)
        progress = self._smoothstep(self.hue_elapsed / self.hue_duration)
        difference = (self.target_hue - self.hue + 0.5) % 1.0 - 0.5
        hue = (self.hue + difference * progress) % 1.0
        return tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, 0.9, 1.0)
        )

    def _advance_offset(self, delta_seconds):
        self.offset_fraction += (
            self.move_direction * delta_seconds / self.translation_duration
        )
        while self.offset_fraction < 0 or self.offset_fraction > 1:
            if self.offset_fraction > 1:
                self.offset_fraction = 2 - self.offset_fraction
                self.move_direction = -1.0
            else:
                self.offset_fraction = -self.offset_fraction
                self.move_direction = 1.0
            self.translation_duration = self.generator.uniform(*self.TRANSLATION_DURATION_RANGE)

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.rotation_change_remaining -= delta_seconds
        if self.rotation_change_remaining <= 0:
            self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
            self.rotation_change_remaining = self.generator.uniform(*self.ROTATION_CHANGE_RANGE)
        for axis in range(3):
            self.angles[axis] = (
                self.angles[axis] + self.angular_speeds[axis] * delta_seconds
            ) % (2 * math.pi)

        self._advance_offset(delta_seconds)
        color = self._advance_hue(delta_seconds)
        normal = self._normal()
        projections = [
            sum(coordinate * component for coordinate, component in zip(position, normal))
            for position in self.positions
        ]
        minimum_projection = min(projections)
        maximum_projection = max(projections)
        plane_offset = minimum_projection + self.offset_fraction * (
            maximum_projection - minimum_projection
        )
        half_thickness = self.thickness / 2
        return [
            color if abs(projection - plane_offset) <= half_thickness else (0, 0, 0)
            for projection in projections
        ]
