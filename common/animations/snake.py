import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class SnakeAnimation(Animation):
    name = "snake"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A bright snake leaves a fading trail before an expanding 3D burst."

    TRAIL_FADE_SECONDS = 24.0
    FULL_TREE_THRESHOLD = 0.06
    TRAVERSE_DURATION_RANGE = (7.0, 12.0)
    SPEED_CHANGE_RANGE = (0.5, 1.6)
    FLASH_COUNT = 2
    FLASH_HALF_PERIOD_SECONDS = 0.14

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
        self.led_spacing = self._estimate_led_spacing()
        self.running = True
        self._begin_cycle()

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
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    def _estimate_led_spacing(self):
        if len(self.positions) < 2:
            return 1.0
        distances = [
            math.sqrt(sum((first[axis] - second[axis]) ** 2 for axis in range(3)))
            for first, second in zip(self.positions, self.positions[1:])
        ]
        positive_distances = [distance for distance in distances if distance > 0]
        return sum(positive_distances) / len(positive_distances) if positive_distances else 1.0

    def _random_color(self):
        hue = self.generator.random()
        return tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, 0.92, 1.0)
        )

    def _begin_cycle(self):
        self.color = self._random_color()
        self.trail_levels = [0.0] * self.led_count
        self.head_position = self.generator.uniform(0, self.led_count - 1)
        self.trail_levels[round(self.head_position)] = 1.0
        self.direction = self.generator.choice((-1.0, 1.0))
        self._choose_speed()
        self.speed_change_remaining = self.generator.uniform(*self.SPEED_CHANGE_RANGE)
        self.phase = "crawl"
        self.explosion_radius = 0.0
        self.flash_elapsed = 0.0

    def _choose_speed(self):
        traversal_seconds = self.generator.uniform(*self.TRAVERSE_DURATION_RANGE)
        self.speed = max(1.0, self.led_count - 1) / traversal_seconds

    def _mark_head_path(self, start, end):
        first_index = round(start)
        last_index = round(end)
        step = 1 if last_index >= first_index else -1
        for index in range(first_index, last_index + step, step):
            self.trail_levels[min(self.led_count - 1, max(0, index))] = 1.0

    def _move_head(self, delta_seconds):
        if self.led_count == 1:
            self.trail_levels[0] = 1.0
            return

        remaining = delta_seconds
        while remaining > 0:
            boundary = self.led_count - 1 if self.direction > 0 else 0
            distance = abs(boundary - self.head_position)
            if distance <= 1e-12:
                self.direction *= -1.0
                continue
            time_to_boundary = distance / self.speed
            step_time = min(remaining, time_to_boundary)
            previous = self.head_position
            self.head_position += self.direction * self.speed * step_time
            self._mark_head_path(previous, self.head_position)
            remaining -= step_time
            if step_time >= time_to_boundary - 1e-12:
                self.head_position = float(boundary)
                self.direction *= -1.0

    def _start_explosion(self):
        head_index = min(self.led_count - 1, max(0, round(self.head_position)))
        self.explosion_center = self.positions[head_index]
        self.trail_levels = [0.0] * self.led_count
        self.explosion_max_radius = max(
            math.sqrt(
                sum((position[axis] - self.explosion_center[axis]) ** 2 for axis in range(3))
            )
            for position in self.positions
        )
        self.explosion_max_radius = max(self.explosion_max_radius, self.led_spacing)
        self.explosion_radius = max(self.led_spacing * 0.5, 0.0)
        self.explosion_speed = self.explosion_max_radius / self.generator.uniform(0.8, 1.6)
        self.phase = "explosion"

    def _crawl_frame(self, delta_seconds):
        fade = math.exp(-delta_seconds / self.TRAIL_FADE_SECONDS)
        self.trail_levels = [level * fade for level in self.trail_levels]
        self._move_head(delta_seconds)
        if self.speed_change_remaining <= 0:
            self._choose_speed()
            self.speed_change_remaining = self.generator.uniform(*self.SPEED_CHANGE_RANGE)
        else:
            self.speed_change_remaining -= delta_seconds
        head_index = min(self.led_count - 1, max(0, round(self.head_position)))
        self.trail_levels[head_index] = 1.0
        if all(level >= self.FULL_TREE_THRESHOLD for level in self.trail_levels):
            self._start_explosion()

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        if self.phase == "crawl":
            self._crawl_frame(delta_seconds)
        elif self.phase == "explosion":
            self.explosion_radius = min(
                self.explosion_max_radius,
                self.explosion_radius + self.explosion_speed * delta_seconds,
            )
            if self.explosion_radius >= self.explosion_max_radius:
                self.phase = "flashing"
                self.flash_elapsed = 0.0
        else:
            self.flash_elapsed += delta_seconds
            flash_duration = self.FLASH_COUNT * 2 * self.FLASH_HALF_PERIOD_SECONDS
            if self.flash_elapsed >= flash_duration:
                self._begin_cycle()

        if self.phase == "crawl":
            return [
                tuple(round(channel * level) for channel in self.color)
                for level in self.trail_levels
            ]
        if self.phase == "explosion":
            return [
                self.color
                if math.sqrt(
                    sum((position[axis] - self.explosion_center[axis]) ** 2 for axis in range(3))
                ) <= self.explosion_radius
                else (0, 0, 0)
                for position in self.positions
            ]

        flash_half_period = int(self.flash_elapsed / self.FLASH_HALF_PERIOD_SECONDS)
        brightness = 1.0 if flash_half_period % 2 == 0 else 0.08
        return [
            tuple(round(channel * brightness) for channel in self.color)
            for _ in range(self.led_count)
        ]

    def stop(self) -> None:
        self.running = False