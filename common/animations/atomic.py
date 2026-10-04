import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class AtomicAnimation(Animation):
    name = "atomic"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A colored sphere expands through the tree, contracts, and repeats."

    PHASE_DURATION_RANGE = (1.5, 3.5)
    POINT_RADIUS_SPACING_FRACTION = 0.12
    SOFT_EDGE_FRACTION = 0.15

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
        self.led_spacing = self._estimate_led_spacing()
        self.point_radius = max(
            self.led_spacing * self.POINT_RADIUS_SPACING_FRACTION,
            self.height * 0.002,
        )
        self.previous_color = None
        self.running = True
        self._begin_expansion()

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
            return self.height / 10
        distances = [
            math.sqrt(sum((first[axis] - second[axis]) ** 2 for axis in range(3)))
            for first, second in zip(self.positions, self.positions[1:])
        ]
        positive_distances = [distance for distance in distances if distance > 0]
        return sum(positive_distances) / len(positive_distances) if positive_distances else self.height / 10

    def _random_color(self):
        while True:
            hue = self.generator.random()
            color = tuple(
                round(channel * 255)
                for channel in colorsys.hsv_to_rgb(hue, 0.9, 1.0)
            )
            if color != self.previous_color:
                self.previous_color = color
                return color

    def _begin_expansion(self):
        self.center = (
            0.0,
            0.0,
            self.generator.uniform(self.minimum_z, self.maximum_z),
        )
        self.point_index = min(
            range(self.led_count),
            key=lambda index: sum(
                (self.positions[index][axis] - self.center[axis]) ** 2
                for axis in range(3)
            ),
        )
        self.color = self._random_color()
        self.maximum_radius = max(
            math.sqrt(
                sum((position[axis] - self.center[axis]) ** 2 for axis in range(3))
            )
            for position in self.positions
        ) * 1.05
        self.phase = "expanding"
        self.phase_start_radius = 0.0
        self.phase_end_radius = self.maximum_radius
        self.phase_elapsed = 0.0
        self.phase_duration = self.generator.uniform(*self.PHASE_DURATION_RANGE)
        self.radius = 0.0

    def _begin_contraction(self):
        self.phase = "contracting"
        self.phase_start_radius = self.maximum_radius
        self.phase_end_radius = 0.0
        self.phase_elapsed = 0.0
        self.phase_duration = self.generator.uniform(*self.PHASE_DURATION_RANGE)
        self.radius = self.maximum_radius

    @staticmethod
    def _smoothstep(progress):
        progress = min(1.0, max(0.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _advance_phase(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            time_left = self.phase_duration - self.phase_elapsed
            step = min(remaining, time_left)
            self.phase_elapsed += step
            remaining -= step
            progress = self._smoothstep(self.phase_elapsed / self.phase_duration)
            self.radius = self.phase_start_radius + (
                self.phase_end_radius - self.phase_start_radius
            ) * progress

            if self.phase_elapsed >= self.phase_duration:
                if self.phase == "expanding":
                    self.radius = self.maximum_radius
                    self._begin_contraction()
                else:
                    self.radius = 0.0
                    self._begin_expansion()

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_phase(delta_seconds)
        if self.radius <= self.point_radius:
            frame = [(0, 0, 0)] * self.led_count
            frame[self.point_index] = self.color
            return frame

        edge_start = self.radius * (1.0 - self.SOFT_EDGE_FRACTION)
        frame = []
        for position in self.positions:
            distance = math.sqrt(
                sum((position[axis] - self.center[axis]) ** 2 for axis in range(3))
            )
            if distance <= edge_start:
                intensity = 1.0
            elif distance <= self.radius:
                intensity = (self.radius - distance) / max(
                    self.radius - edge_start,
                    1e-9,
                )
            else:
                intensity = 0.0
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame

    def stop(self) -> None:
        self.running = False