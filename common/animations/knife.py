import colorsys
import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class KnifeAnimation(Animation):
    name = "knife"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "One or two rotating vertical color planes with smooth hue shifts."

    ROTATION_DURATION_RANGE = (2.0, 5.0)
    MIN_HUE_SEPARATION = 0.1

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
        self.plane_count = self.generator.choice((1, 2))
        self.sector_count = self.plane_count * 2
        self.rotation_step = 2 * math.pi / self.sector_count
        self.rotation_angle = self.generator.uniform(0.0, 2 * math.pi)
        self.rotation_direction = self.generator.choice((-1.0, 1.0))
        self.rotation_duration = self.generator.uniform(*self.ROTATION_DURATION_RANGE)
        self.rotation_elapsed = 0.0
        self.current_hues = self._new_hues()
        self.target_hues = self._new_hues(self.current_hues)
        self.running = True

    def _new_hues(self, previous=None):
        minimum = max(self.MIN_HUE_SEPARATION, 1 / self.sector_count * 0.4)
        hues = []
        attempts = 0
        while len(hues) < self.sector_count and attempts < 2048:
            attempts += 1
            hue = self.generator.random()
            if any(
                min(abs(hue - existing), 1 - abs(hue - existing)) < minimum
                for existing in hues
            ):
                continue
            if previous is not None:
                old_hue = previous[len(hues)]
                if min(abs(hue - old_hue), 1 - abs(hue - old_hue)) < 0.035:
                    continue
            hues.append(hue)
        if len(hues) < self.sector_count:
            base = self.generator.random()
            hues = [(base + index / self.sector_count) % 1.0 for index in range(self.sector_count)]
        self.generator.shuffle(hues)
        return hues

    @staticmethod
    def _hue_color(hue):
        return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 0.92, 1.0))

    @staticmethod
    def _interpolate_hue(start, end, amount):
        delta = (end - start + 0.5) % 1.0 - 0.5
        return (start + delta * amount) % 1.0

    def _advance_rotation(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            time_left = self.rotation_duration - self.rotation_elapsed
            step = min(remaining, time_left)
            self.rotation_angle = (
                self.rotation_angle
                + self.rotation_direction * self.rotation_step * step / self.rotation_duration
            ) % (2 * math.pi)
            self.rotation_elapsed += step
            remaining -= step

            if self.rotation_elapsed >= self.rotation_duration:
                self.current_hues = self.target_hues
                self.target_hues = self._new_hues(self.current_hues)
                self.rotation_elapsed = 0.0
                self.rotation_duration = self.generator.uniform(*self.ROTATION_DURATION_RANGE)
                self.rotation_direction = self.generator.choice((-1.0, 1.0))

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_rotation(delta_seconds)
        progress = self.rotation_elapsed / self.rotation_duration
        eased_progress = progress * progress * (3 - 2 * progress)
        frame = []
        for x, y, _z in self.positions:
            relative_angle = (math.atan2(y, x) - self.rotation_angle) % (2 * math.pi)
            sector = min(
                self.sector_count - 1,
                int(relative_angle / self.rotation_step),
            )
            hue = self._interpolate_hue(
                self.current_hues[sector],
                self.target_hues[sector],
                eased_progress,
            )
            frame.append(self._hue_color(hue))
        return frame

