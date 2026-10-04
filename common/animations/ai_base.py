import colorsys
import math
import random
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


def _rgb(hue, saturation=0.9, value=1.0):
    return tuple(
        round(channel * 255)
        for channel in colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    )


def _mix(first, second, amount):
    return tuple(round(a + (b - a) * amount) for a, b in zip(first, second))


def _smooth(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def _distance(first, second):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class SpatialAnimation(Animation, ABC):
    """Shared calibrated-position handling for the bundled showcase effects."""

    @abstractmethod
    def _initialise_effect(self, parameters):
        raise NotImplementedError

    @abstractmethod
    def _render_frame(self, delta_seconds):
        raise NotImplementedError

    def initialise(self, led_count: int, parameters: Mapping[str, object]) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")
        self.led_count = led_count
        self.generator = random.Random()
        raw_positions = parameters.get("positions")
        if isinstance(raw_positions, Sequence) and len(raw_positions) == led_count:
            try:
                positions = [
                    tuple(float(value) for value in position)
                    for position in raw_positions
                ]
                if not all(
                    len(position) == 3
                    and all(math.isfinite(value) for value in position)
                    for position in positions
                ):
                    positions = self._fallback_positions(led_count)
            except (TypeError, ValueError):
                positions = self._fallback_positions(led_count)
        else:
            positions = self._fallback_positions(led_count)

        minimum_z = min(position[2] for position in positions)
        maximum_z = max(position[2] for position in positions)
        self.center_z = (minimum_z + maximum_z) / 2
        radial_extent = max(math.hypot(x, y) for x, y, _z in positions)
        self.scale = max(maximum_z - minimum_z, radial_extent * 2, 1e-6)
        self.positions = [
            (x / self.scale, y / self.scale, (z - minimum_z) / self.scale)
            for x, y, z in positions
        ]
        self.height = max((maximum_z - minimum_z) / self.scale, 1e-6)
        self.tree_radius = radial_extent / self.scale
        self.elapsed = 0.0
        self.running = True
        self._initialise_effect(parameters)

    def _fallback_positions(self, led_count):
        points = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1 - height)
            points.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return points

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")
        self.elapsed += delta_seconds
        frame = list(self._render_frame(delta_seconds))
        if len(frame) != self.led_count:
            raise ValueError(f"Animation returned {len(frame)} LEDs; expected {self.led_count}")
        return frame

    def stop(self) -> None:
        self.running = False
