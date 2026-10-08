import colorsys
import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class FizzyAnimation(Animation):
    name = "fizzy"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "All LEDs share one vivid hue and pulse independently."

    CYCLE_DURATION_RANGE = (0.18, 0.65)

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        generator = random.Random()
        hue = generator.random()
        self.color = tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, 0.92, 1.0)
        )
        self.cycle_durations = []
        self.elapsed_seconds = []
        for _ in range(led_count):
            self.cycle_durations.append(generator.uniform(*self.CYCLE_DURATION_RANGE))
            self.elapsed_seconds.append(generator.random() * self.cycle_durations[-1])
        self.running = True

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        frame = []
        for index, cycle_duration in enumerate(self.cycle_durations):
            elapsed = (self.elapsed_seconds[index] + delta_seconds) % cycle_duration
            self.elapsed_seconds[index] = elapsed
            phase = 2 * math.pi * elapsed / cycle_duration
            brightness = (1 - math.cos(phase)) / 2
            frame.append(
                tuple(round(channel * brightness) for channel in self.color)
            )
        return frame

    def stop(self) -> None:
        super().stop()
        self.elapsed_seconds = [0.0] * self.led_count