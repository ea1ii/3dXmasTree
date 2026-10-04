import math
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class ZarathustraIntroAnimation(Animation):
    name = "zarathustra_intro"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A two-minute sunrise build into a bright, sustained fanfare."
    duration_seconds = 120.0

    COLORS = (
        (34, 0, 3),
        (190, 25, 3),
        (255, 92, 8),
        (255, 178, 28),
        (255, 222, 142),
        (255, 250, 224),
    )

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.positions = self._read_positions(parameters.get("positions"), led_count)
        self.minimum_z = min(position[2] for position in self.positions)
        self.maximum_z = max(position[2] for position in self.positions)
        self.height = self.maximum_z - self.minimum_z
        if self.height <= 0:
            self.height = 1.0
            self.maximum_z = self.minimum_z + self.height
        self.elapsed_seconds = 0.0
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
        return [
            (
                0.42 * (1 - index / max(1, led_count - 1))
                * math.cos(index * 2.399963229728653),
                0.42 * (1 - index / max(1, led_count - 1))
                * math.sin(index * 2.399963229728653),
                index / max(1, led_count - 1),
            )
            for index in range(led_count)
        ]

    @staticmethod
    def _smoothstep(value):
        value = min(1.0, max(0.0, value))
        return value * value * (3 - 2 * value)

    @staticmethod
    def _mix_colors(first, second, amount):
        return tuple(
            round(start + (end - start) * amount)
            for start, end in zip(first, second)
        )

    def _scene_values(self, elapsed_seconds):
        if elapsed_seconds < 18.0:
            progress = self._smoothstep(elapsed_seconds / 18.0)
            return (
                self._mix_colors(self.COLORS[0], self.COLORS[2], progress),
                0.06 + 0.27 * progress,
                "sunrise",
            )
        if elapsed_seconds < 50.0:
            progress = (elapsed_seconds - 18.0) / 32.0
            pulse = 0.78 + 0.22 * max(
                0.0,
                math.sin(2 * math.pi * (elapsed_seconds - 18.0) / 2.5),
            ) ** 3
            return (
                self._mix_colors(self.COLORS[2], self.COLORS[3], self._smoothstep(progress)),
                (0.36 + 0.22 * progress) * pulse,
                "rise",
            )
        if elapsed_seconds < 80.0:
            progress = (elapsed_seconds - 50.0) / 30.0
            pulse = 0.60 + 0.40 * max(
                0.0,
                math.sin(2 * math.pi * (elapsed_seconds - 50.0) / 1.8),
            ) ** 4
            return (
                self._mix_colors(self.COLORS[3], self.COLORS[4], self._smoothstep(progress)),
                (0.58 + 0.19 * progress) * pulse,
                "surge",
            )
        if elapsed_seconds < 104.0:
            progress = (elapsed_seconds - 80.0) / 24.0
            pulse = 0.72 + 0.28 * max(
                0.0,
                math.sin(2 * math.pi * (elapsed_seconds - 80.0) / 0.9),
            ) ** 6
            return (
                self._mix_colors(self.COLORS[4], self.COLORS[5], self._smoothstep(progress)),
                (0.78 + 0.17 * progress) * pulse,
                "fanfare",
            )
        if elapsed_seconds < 116.0:
            progress = self._smoothstep((elapsed_seconds - 104.0) / 12.0)
            return (
                self._mix_colors(self.COLORS[4], self.COLORS[5], progress),
                0.95 + 0.05 * progress,
                "climax",
            )
        return self.COLORS[5], 1.0, "finale"

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self.elapsed_seconds = min(
            self.duration_seconds,
            self.elapsed_seconds + delta_seconds,
        )
        base_color, intensity, section = self._scene_values(self.elapsed_seconds)
        frame = []
        for x, y, z in self.positions:
            height = (z - self.minimum_z) / self.height
            if section == "sunrise":
                activation = self._smoothstep(
                    self.elapsed_seconds / 18.0 * 1.22 - height + 0.08
                )
                local_intensity = intensity * activation
            elif section == "rise":
                phase = (
                    2 * math.pi * (self.elapsed_seconds - 18.0) / 5.0
                    - height * math.pi * 1.5
                    + math.atan2(y, x) * 0.18
                )
                local_intensity = intensity * (0.88 + 0.12 * (0.5 + 0.5 * math.sin(phase)))
            elif section in ("surge", "fanfare"):
                phase = (
                    2 * math.pi * self.elapsed_seconds / (1.8 if section == "surge" else 0.9)
                    - height * math.pi * 2.0
                    + math.atan2(y, x) * 0.3
                )
                local_intensity = intensity * (0.82 + 0.18 * (0.5 + 0.5 * math.sin(phase)))
            else:
                local_intensity = intensity
            frame.append(
                tuple(round(channel * local_intensity) for channel in base_color)
            )
        return frame

    def stop(self) -> None:
        self.running = False