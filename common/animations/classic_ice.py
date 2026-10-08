import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class ClassicIceAnimation(Animation):
    name = "classic_ice"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Slow warm-white glow with unsynchronized cold-white flashes that fade in and out."

    WARM_WHITE = (255, 190, 120)
    COLD_WHITE = (220, 240, 255)
    GLOW_CYCLE_SECONDS = 6.0
    FLASH_PERCENT_RANGE = (0.05, 0.10)
    FLASH_DURATION_RANGE = (0.1, 5.0)
    FLASH_RISE_FRACTION = 0.15

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.generator = random.Random()
        self.glow_elapsed = 0.0
        self.flash_duration = [0.0] * led_count
        self.flash_remaining = [0.0] * led_count
        self.flash_delay = []
        for _ in range(led_count):
            duration = self.generator.uniform(*self.FLASH_DURATION_RANGE)
            duty_target = self.generator.uniform(*self.FLASH_PERCENT_RANGE)
            period = duration / duty_target
            self.flash_delay.append(self.generator.uniform(0.0, period))
        self.running = True

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.glow_elapsed = (
            self.glow_elapsed + delta_seconds
        ) % self.GLOW_CYCLE_SECONDS
        for index in range(self.led_count):
            self.flash_remaining[index] = max(
                0.0, self.flash_remaining[index] - delta_seconds
            )
            self.flash_delay[index] -= delta_seconds
            if self.flash_delay[index] <= 0:
                duration = self.generator.uniform(*self.FLASH_DURATION_RANGE)
                duty_target = self.generator.uniform(*self.FLASH_PERCENT_RANGE)
                self.flash_duration[index] = duration
                self.flash_remaining[index] = duration
                self.flash_delay[index] = duration / duty_target

        glow = (1 - math.cos(2 * math.pi * self.glow_elapsed / self.GLOW_CYCLE_SECONDS)) / 2
        warm_color = tuple(round(channel * glow) for channel in self.WARM_WHITE)
        frame = []
        for index in range(self.led_count):
            remaining = self.flash_remaining[index]
            if remaining <= 0:
                frame.append(warm_color)
                continue

            duration = self.flash_duration[index]
            elapsed = duration - remaining
            fade_in_duration = duration * self.FLASH_RISE_FRACTION
            if elapsed < fade_in_duration:
                brightness = elapsed / fade_in_duration
            else:
                fade_out_progress = (elapsed - fade_in_duration) / (
                    duration - fade_in_duration
                )
                brightness = 1.0 - fade_out_progress
            brightness = min(1.0, max(0.0, brightness))
            frame.append(
                tuple(
                    round(warm * (1 - brightness) + cold * brightness)
                    for warm, cold in zip(warm_color, self.COLD_WHITE)
                )
            )
        return frame

    def stop(self) -> None:
        super().stop()
        self.flash_duration = [0.0] * self.led_count
        self.flash_remaining = [0.0] * self.led_count