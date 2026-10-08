import colorsys
import math
import random
from collections.abc import Mapping

from common.animations import Animation, LEDFrame


class HanoiAnimation(Animation):
    name = "hanoi"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Random-color slices stack, flash on landing, then rise away to reset."

    SLICE_COUNT_LIMIT = 12
    FALL_SPEED_RANGE = (0.45, 1.0)
    FLASH_HALF_PERIOD_SECONDS = 0.1
    FLASH_COUNT = 3
    EMPTY_HOLD_SECONDS = 0.3

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

        self.slice_count = min(
            self.SLICE_COUNT_LIMIT,
            max(2, round(math.sqrt(led_count))),
        )
        self.slice_height = self.height / self.slice_count
        self.stack_count = 0
        self.settled_colors = []
        self.running = True
        self._begin_next_slice()

    def _random_color(self):
        hue = self.generator.random()
        return tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, 0.88, 1.0)
        )

    def _begin_next_slice(self):
        if self.stack_count >= self.slice_count:
            self.stack_count = 0
            self.settled_colors.clear()

        self.current_color = self._random_color()
        self.active_center = self.maximum_z + self.slice_height / 2
        self.target_center = (
            self.minimum_z + (self.stack_count + 0.5) * self.slice_height
        )
        self.fall_speed = self.height * self.generator.uniform(*self.FALL_SPEED_RANGE)
        self.phase = "falling"
        self.flash_elapsed = 0.0

    def _land_slice(self):
        settled_color = (
            self.current_color if self.stack_count == 0 else self.settled_colors[-1]
        )
        self.settled_colors.append(settled_color)
        self.stack_count += 1
        if self.stack_count >= self.slice_count:
            self._begin_clearing_slice()
        else:
            self._begin_next_slice()

    def _begin_clearing_slice(self):
        self.phase = "clearing"
        self.clear_index = self.stack_count - 1
        self.active_center = self.minimum_z + (self.clear_index + 0.5) * self.slice_height
        self.clear_target_center = self.maximum_z + self.slice_height
        self.clear_speed = self.height * self.generator.uniform(*self.FALL_SPEED_RANGE)

    def _advance_state(self, delta_seconds):
        remaining = delta_seconds
        flash_duration = self.FLASH_COUNT * 2 * self.FLASH_HALF_PERIOD_SECONDS
        while remaining > 0:
            if self.phase == "falling":
                distance = max(0.0, self.active_center - self.target_center)
                time_to_land = distance / self.fall_speed
                if remaining < time_to_land:
                    self.active_center -= self.fall_speed * remaining
                    return
                self.active_center = self.target_center
                remaining -= time_to_land
                if self.stack_count == 0:
                    self._land_slice()
                else:
                    self.phase = "flashing"
                    self.flash_elapsed = 0.0
            elif self.phase == "flashing":
                time_to_settle = flash_duration - self.flash_elapsed
                if remaining < time_to_settle - 1e-9:
                    self.flash_elapsed += remaining
                    return
                remaining = max(0.0, remaining - time_to_settle)
                self._land_slice()
            elif self.phase == "clearing":
                distance = max(0.0, self.clear_target_center - self.active_center)
                time_to_clear = distance / self.clear_speed
                if remaining < time_to_clear:
                    self.active_center += self.clear_speed * remaining
                    return
                self.active_center = self.clear_target_center
                remaining = max(0.0, remaining - time_to_clear)
                self.settled_colors.pop()
                self.stack_count -= 1
                if self.stack_count == 0:
                    self.phase = "empty"
                    self.empty_remaining = self.EMPTY_HOLD_SECONDS
                else:
                    self._begin_clearing_slice()
            else:
                if remaining < self.empty_remaining:
                    self.empty_remaining -= remaining
                    return
                remaining -= self.empty_remaining
                self._begin_next_slice()

    def _layer_index(self, z):
        index = int((z - self.minimum_z) / self.slice_height)
        return min(self.slice_count - 1, max(0, index))

    def _frame_color_for_active_slice(self):
        if self.phase == "falling":
            return self.current_color
        flash_half_period = min(
            self.FLASH_COUNT * 2 - 1,
            int((self.flash_elapsed + 1e-9) / self.FLASH_HALF_PERIOD_SECONDS),
        )
        if flash_half_period % 2 == 0:
            return self.current_color
        return self.settled_colors[-1]

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_state(delta_seconds)
        frame = []
        for _x, _y, z in self.positions:
            layer = self._layer_index(z)
            if self.phase == "clearing":
                if abs(z - self.active_center) <= self.slice_height / 2:
                    color = self.settled_colors[self.clear_index]
                elif layer < self.stack_count and layer != self.clear_index:
                    color = self.settled_colors[layer]
                else:
                    color = (0, 0, 0)
            elif layer < self.stack_count:
                color = self.settled_colors[layer]
            elif self.phase == "falling" and abs(z - self.active_center) <= self.slice_height / 2:
                color = self.current_color
            elif self.phase == "flashing" and layer == self.stack_count:
                color = self._frame_color_for_active_slice()
            else:
                color = (0, 0, 0)
            frame.append(color)
        return frame

