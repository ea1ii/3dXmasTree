import math
from pathlib import Path

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class AuroraCurtain(SpatialAnimation):
    name = "ai_aurora_curtain"
    author = "Carlos Gil & AI"
    description = "Green, turquoise, and violet curtains ripple through 3D space."

    SPEED_RANGE = (0.15, 0.3)
    PARAMETER_DEFAULTS = {
        "speed_range": SPEED_RANGE
    }

    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(self, parameters):
        effect_parameters = self._load_effect_parameters(parameters, self.name)
        self.speed_range = effect_parameters["speed_range"]
        self.phase = self.generator.uniform(0, 2 * math.pi)
        self.speed = self.generator.uniform(*self.speed_range)

    @classmethod
    def _load_effect_parameters(cls, parameters, effect_name):
        configured = super()._merge_effect_parameters(
            parameters,
            effect_name,
            cls.PARAMETER_DEFAULTS,
            cls.PARAMETER_SIDECAR,
        )
        speed_range = cls._read_range(
            configured["speed_range"],
            "speed_range",
            0.0,
            math.inf,
            minimum_exclusive=True,
        )
        effective_parameters = {"speed_range": speed_range}
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x)
            wave = 0.5 + 0.5 * math.sin(
                z * 9 + math.sin(angle * 3 + self.elapsed * 0.3 + self.phase) * 1.8
                - self.elapsed * self.speed
            )
            secondary = 0.5 + 0.5 * math.sin(angle * 5 - z * 6 + self.elapsed * 0.22)
            hue = 0.32 + 0.42 * (0.65 * wave + 0.35 * secondary)
            intensity = 0.25 + 0.75 * wave
            frame.append(tuple(round(channel * intensity) for channel in _rgb(hue, 0.8, 1)))
        return frame
