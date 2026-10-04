import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class GaliciaAnimation(Animation):
    name = "galicia"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A thick cyan band sweeps through a cold-white 3D tree."

    COLD_WHITE = (210, 240, 255)
    CYAN = (0, 255, 255)
    SWEEP_DURATION_RANGE = (1.5, 4.0)

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
        self.tree_radius = max(
            math.hypot(position[0], position[1])
            for position in self.positions
        )
        if self.tree_radius <= 0:
            self.tree_radius = max(
                (max(position[2] for position in self.positions)
                 - min(position[2] for position in self.positions)) * 0.34,
                0.5,
            )
        self.tree_diameter = self.tree_radius * 2
        self.stripe_width = self.tree_diameter * 0.25
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
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    def _random_direction(self):
        vertical = self.generator.uniform(-1.0, 1.0)
        azimuth = self.generator.uniform(0.0, 2 * math.pi)
        horizontal = math.sqrt(1.0 - vertical * vertical)
        return (
            horizontal * math.cos(azimuth),
            horizontal * math.sin(azimuth),
            vertical,
        )

    def _start_sweep(self):
        self.direction = self._random_direction()
        self.projections = [
            sum(coordinate * component for coordinate, component in zip(position, self.direction))
            for position in self.positions
        ]
        self.minimum_projection = min(self.projections)
        self.maximum_projection = max(self.projections)
        self.projection_span = max(
            self.maximum_projection - self.minimum_projection,
            self.stripe_width,
        )
        self.sweep_direction = self.generator.choice((-1.0, 1.0))
        self.sweep_duration = self.generator.uniform(*self.SWEEP_DURATION_RANGE)
        self.sweep_elapsed = 0.0

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.sweep_elapsed += delta_seconds
        if self.sweep_elapsed >= self.sweep_duration:
            self._start_sweep()

        progress = self.sweep_elapsed / self.sweep_duration
        if self.sweep_direction > 0:
            stripe_center = self.minimum_projection + progress * self.projection_span
        else:
            stripe_center = self.maximum_projection - progress * self.projection_span
        half_width = self.stripe_width / 2
        return [
            self.CYAN
            if abs(projection - stripe_center) <= half_width
            else self.COLD_WHITE
            for projection in self.projections
        ]

    def stop(self) -> None:
        self.running = False