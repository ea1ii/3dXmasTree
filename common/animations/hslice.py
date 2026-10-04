import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class HorizontalSliceAnimation(Animation):
    name = "hslice"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A bouncing horizontal plane divides two changing contrasting hues."

    HUE_SEPARATION_RANGE = (1 / 3, 0.5)
    HALF_SWEEP_SECONDS_RANGE = (1.0, 5.0)

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

        margin = self.height * 0.001
        self.bottom = self.minimum_z - margin
        self.top = self.maximum_z + margin
        self.plane_z = self.top
        self.direction = -1.0
        self.speed = self._random_speed()
        self.below_hue = self.generator.random()
        self.above_hue = self._contrasting_hue(self.below_hue)
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
        return HorizontalSliceAnimation._fallback_positions(led_count)

    @staticmethod
    def _fallback_positions(led_count):
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    def _contrasting_hue(self, reference_hue):
        separation = self.generator.uniform(*self.HUE_SEPARATION_RANGE)
        direction = self.generator.choice((-1.0, 1.0))
        return (reference_hue + direction * separation) % 1.0

    @staticmethod
    def _hue_color(hue):
        return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 0.92, 1.0))

    def _random_speed(self):
        return self.height / self.generator.uniform(*self.HALF_SWEEP_SECONDS_RANGE)

    def _bounce(self):
        if self.direction < 0:
            self.below_hue = self._contrasting_hue(self.above_hue)
        else:
            self.above_hue = self._contrasting_hue(self.below_hue)
        self.direction *= -1.0
        self.speed = self._random_speed()

    def _advance_plane(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            boundary = self.bottom if self.direction < 0 else self.top
            distance = abs(boundary - self.plane_z)
            time_to_boundary = distance / self.speed
            if remaining < time_to_boundary:
                self.plane_z += self.direction * self.speed * remaining
                return

            self.plane_z = boundary
            remaining -= time_to_boundary
            self._bounce()

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_plane(delta_seconds)
        below_color = self._hue_color(self.below_hue)
        above_color = self._hue_color(self.above_hue)
        return [
            above_color if z >= self.plane_z else below_color
            for _x, _y, z in self.positions
        ]

    def stop(self) -> None:
        self.running = False