import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class FrontsAnimation(Animation):
    name = "fronts"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Fast, randomly oriented 3D fronts fill the tree with new colors."

    SWEEP_DURATION_RANGE = (0.5, 2.0)

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
        self._start_sweep()
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
        return FrontsAnimation._fallback_positions(led_count)

    @staticmethod
    def _fallback_positions(led_count):
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    def _random_normal(self):
        vertical = self.generator.uniform(-1.0, 1.0)
        azimuth = self.generator.uniform(0.0, 2 * math.pi)
        horizontal = math.sqrt(1.0 - vertical * vertical)
        return (
            horizontal * math.cos(azimuth),
            horizontal * math.sin(azimuth),
            vertical,
        )

    def _random_color(self, previous_color=None):
        while True:
            hue = self.generator.random()
            color = tuple(
                round(channel * 255)
                for channel in colorsys.hsv_to_rgb(hue, 0.95, 1.0)
            )
            if color != previous_color:
                return color

    def _start_sweep(self):
        previous_color = getattr(self, "color", None)
        self.background_color = previous_color or (0, 0, 0)
        self.normal = self._random_normal()
        self.projections = [
            sum(coordinate * normal for coordinate, normal in zip(position, self.normal))
            for position in self.positions
        ]
        self.minimum_projection = min(self.projections)
        self.maximum_projection = max(self.projections)
        self.projection_span = self.maximum_projection - self.minimum_projection
        if self.projection_span <= 0:
            self.projection_span = 1.0
            self.maximum_projection = self.minimum_projection + self.projection_span

        self.color = self._random_color(previous_color)
        self.duration = self.generator.uniform(*self.SWEEP_DURATION_RANGE)
        self.margin = self.projection_span * 0.001
        self.speed = (self.projection_span + 2 * self.margin) / self.duration
        self.elapsed_seconds = 0.0
        self.sweep_complete = False

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        if self.sweep_complete:
            self._start_sweep()

        self.elapsed_seconds = min(
            self.duration,
            self.elapsed_seconds + delta_seconds,
        )
        progress = self.elapsed_seconds / self.duration
        plane_offset = self.minimum_projection - self.margin + progress * (
            self.projection_span + 2 * self.margin
        )
        self.sweep_complete = progress >= 1.0

        return [
            self.color if projection <= plane_offset else self.background_color
            for projection in self.projections
        ]

    def stop(self) -> None:
        self.running = False