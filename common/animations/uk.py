import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class UkAnimation(Animation):
    name = "uk"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A Union Jack color cone changes height or angle, then collapses."

    UNION_JACK_COLORS = (
        (220, 20, 45),
        (242, 246, 255),
        (0, 55, 160),
    )
    EXPANSION_DURATION_RANGE = (1.5, 3.5)
    COLLAPSE_DURATION_RANGE = (0.35, 0.8)

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
        self.apex_clearance = self.height * 0.25
        self.apex_z = self.maximum_z + self.apex_clearance
        self.cone_height = self.apex_z - self.minimum_z
        self.base_radius = max(
            math.hypot(position[0], position[1])
            * self.cone_height
            / (self.apex_z - position[2])
            for position in self.positions
        ) * 1.05
        if self.base_radius <= 0:
            self.base_radius = self.height * 0.34
        self.color = self.generator.choice(self.UNION_JACK_COLORS)
        self.shape_mode = self.generator.choice(("height", "angle"))
        self.phase = "expanding"
        self.progress = 0.0
        self.phase_elapsed = 0.0
        self.phase_duration = self.generator.uniform(*self.EXPANSION_DURATION_RANGE)
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

    @staticmethod
    def _smoothstep(progress):
        progress = min(1.0, max(0.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _next_cycle(self):
        self.color = self.generator.choice(self.UNION_JACK_COLORS)
        self.shape_mode = self.generator.choice(("height", "angle"))
        self.phase = "expanding"
        self.progress = 0.0
        self.phase_elapsed = 0.0
        self.phase_duration = self.generator.uniform(*self.EXPANSION_DURATION_RANGE)

    def _advance(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            time_left = self.phase_duration - self.phase_elapsed
            step = min(remaining, time_left)
            self.phase_elapsed += step
            remaining -= step
            eased = self._smoothstep(self.phase_elapsed / self.phase_duration)
            self.progress = eased if self.phase == "expanding" else 1.0 - eased

            if self.phase_elapsed >= self.phase_duration:
                if self.phase == "expanding":
                    self.phase = "contracting"
                    self.phase_elapsed = 0.0
                    self.phase_duration = self.generator.uniform(*self.COLLAPSE_DURATION_RANGE)
                    self.progress = 1.0
                else:
                    self._next_cycle()

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance(delta_seconds)
        if self.progress >= 1.0:
            return [self.color] * self.led_count

        frame = []
        for x, y, z in self.positions:
            depth_below_apex = self.apex_z - z
            if self.shape_mode == "height":
                cone_height = self.cone_height * self.progress
                cone_radius = self.base_radius * depth_below_apex / self.cone_height
                inside = (
                    depth_below_apex <= cone_height
                    and math.hypot(x, y) <= cone_radius
                )
            else:
                cone_radius = (
                    self.base_radius * self.progress * depth_below_apex / self.cone_height
                )
                inside = (
                    depth_below_apex <= self.cone_height
                    and math.hypot(x, y) <= cone_radius
                )
            frame.append(self.color if inside else (0, 0, 0))
        return frame

    def stop(self) -> None:
        self.running = False