import math
from collections.abc import Mapping

from common.animations import Animation, LEDColor, LEDFrame


class BlinkAnimation(Animation):
    name = "blink"
    author = "3dXmasTree"
    version = "0.1.0"
    description = "Blink all LEDs on and off at configurable intervals."

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.on_seconds = float(parameters.get("on_seconds", 0.5))
        self.off_seconds = float(parameters.get("off_seconds", 0.5))
        color = parameters.get("color", (255, 255, 255))
        if not isinstance(color, (tuple, list)) or len(color) != 3:
            raise ValueError("color must be an RGB tuple with three channels")
        self.color = tuple(int(channel) for channel in color)
        if any(channel < 0 or channel > 255 for channel in self.color):
            raise ValueError("RGB channels must be between 0 and 255")
        if (
            not math.isfinite(self.on_seconds)
            or not math.isfinite(self.off_seconds)
            or self.on_seconds <= 0
            or self.off_seconds <= 0
        ):
            raise ValueError("on_seconds and off_seconds must be finite and positive")

        self.elapsed_seconds = 0.0
        self.running = True

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.elapsed_seconds += delta_seconds
        cycle_seconds = self.on_seconds + self.off_seconds
        is_on = self.elapsed_seconds % cycle_seconds < self.on_seconds
        color: LEDColor = self.color if is_on else (0, 0, 0)
        return [color] * self.led_count

    def stop(self) -> None:
        self.running = False
        self.elapsed_seconds = 0.0
