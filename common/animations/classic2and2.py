import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class Classic2And2Animation(Animation):
    name = "classic2and2"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Alternate red/green and blue/amber pairs with random switches or crossfades."

    RED = (255, 0, 0)
    BLUE = (0, 0, 255)
    GREEN = (0, 255, 0)
    AMBER = (255, 191, 0)
    OFF = (0, 0, 0)
    SWITCH_INTERVAL_RANGE = (0.5, 3.0)
    CROSSFADE_DURATION_RANGE = (0.15, 0.45)

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.generator = random.Random()
        self.groups = [min(3, index * 4 // led_count) for index in range(led_count)]
        self.blue_amber_active = False
        self.transition_from_blue_amber_active = False
        self.transition_elapsed = 0.0
        self.transition_duration = 0.0
        self.switch_remaining = self.generator.uniform(*self.SWITCH_INTERVAL_RANGE)
        self.running = True

    @staticmethod
    def _group_color(group: int, blue_amber_active: bool):
        if group == 0:
            return (
                Classic2And2Animation.OFF
                if blue_amber_active
                else Classic2And2Animation.RED
            )
        if group == 1:
            return (
                Classic2And2Animation.BLUE
                if blue_amber_active
                else Classic2And2Animation.OFF
            )
        if group == 2:
            return (
                Classic2And2Animation.GREEN
                if not blue_amber_active
                else Classic2And2Animation.OFF
            )
        return (
            Classic2And2Animation.AMBER
            if blue_amber_active
            else Classic2And2Animation.OFF
        )

    @staticmethod
    def _blend(first, second, amount):
        return tuple(
            round(start + (end - start) * amount)
            for start, end in zip(first, second)
        )

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.switch_remaining -= delta_seconds
        if self.switch_remaining <= 0:
            self.transition_from_blue_amber_active = self.blue_amber_active
            self.blue_amber_active = not self.blue_amber_active
            self.switch_remaining = self.generator.uniform(*self.SWITCH_INTERVAL_RANGE)
            if self.generator.choice((False, True)):
                self.transition_duration = self.generator.uniform(
                    *self.CROSSFADE_DURATION_RANGE
                )
                self.transition_elapsed = 0.0
            else:
                self.transition_duration = 0.0

        if self.transition_duration > 0:
            self.transition_elapsed = min(
                self.transition_duration,
                self.transition_elapsed + delta_seconds,
            )
            progress = self.transition_elapsed / self.transition_duration
            amount = progress * progress * (3 - 2 * progress)
        else:
            amount = 1.0

        return [
            self._blend(
                self._group_color(group, self.transition_from_blue_amber_active),
                self._group_color(group, self.blue_amber_active),
                amount,
            )
            for group in self.groups
        ]

    def stop(self) -> None:
        self.running = False