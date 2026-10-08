import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class ClassicFadeAnimation(Animation):
    name = "classic_fade"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Independently fade LEDs with random classic colors or one shared hue."

    COLORS = (
        (220, 240, 255),
        (255, 190, 110),
        (255, 0, 0),
        (135, 206, 235),
    )
    MIN_CYCLE_SECONDS = 0.5
    MAX_CYCLE_SECONDS = 2.0

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        generator = random.Random()
        self.led_count = led_count
        self.same_hue_mode = generator.choice((False, True))
        if self.same_hue_mode:
            shared_color = generator.choice(self.COLORS)
            self.colors = [shared_color] * led_count
        else:
            self.colors = [generator.choice(self.COLORS) for _ in range(led_count)]
        self.cycle_seconds = [
            generator.uniform(self.MIN_CYCLE_SECONDS, self.MAX_CYCLE_SECONDS)
            for _ in range(led_count)
        ]
        self.elapsed_seconds = [
            generator.uniform(0.0, cycle_seconds)
            for cycle_seconds in self.cycle_seconds
        ]
        self.running = True

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        frame = []
        for index, cycle_seconds in enumerate(self.cycle_seconds):
            elapsed = (self.elapsed_seconds[index] + delta_seconds) % cycle_seconds
            self.elapsed_seconds[index] = elapsed
            brightness = (1 - math.cos(2 * math.pi * elapsed / cycle_seconds)) / 2
            frame.append(
                tuple(round(channel * brightness) for channel in self.colors[index])
            )
        return frame

    def stop(self) -> None:
        super().stop()
        self.elapsed_seconds = [0.0] * self.led_count