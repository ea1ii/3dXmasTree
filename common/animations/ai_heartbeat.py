import math
from collections.abc import Mapping
from pathlib import Path

from common.animations.ai_base import SpatialAnimation, _distance, _smooth


class Heartbeat(SpatialAnimation):
    name = "ai_heartbeat"
    author = "Carlos Gil & AI"
    version = "0.2.0"
    description = "A red sphere at the base beats while a dim red glow pulses through the tree."

    EDGE_SOFTNESS = 0.15
    PARAMETER_DEFAULTS = {
        "period_seconds": 1.4,
        "expand_seconds": 0.15,
        "collapse_seconds": 0.7,
        "sphere_radius_fraction": 0.3,
        "base_glow": 0.05,
        "peak_glow": 0.3,
    }
    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(self, parameters: Mapping[str, object]) -> None:
        effect_parameters = self._load_effect_parameters(parameters, self.name)
        self.period = effect_parameters["period_seconds"]
        self.expand = effect_parameters["expand_seconds"]
        self.collapse = effect_parameters["collapse_seconds"]
        self.base_glow = effect_parameters["base_glow"]
        self.peak_glow = effect_parameters["peak_glow"]
        self.base_radius = max(
            self.tree_radius * effect_parameters["sphere_radius_fraction"], 0.05
        )
        self.center = (0.0, 0.0, self.base_radius)

    @classmethod
    def _load_effect_parameters(cls, parameters, effect_name):
        configured = super()._merge_effect_parameters(
            parameters,
            effect_name,
            cls.PARAMETER_DEFAULTS,
            cls.PARAMETER_SIDECAR,
        )

        def read_number(key, lower, upper):
            raw_value = configured[key]
            if isinstance(raw_value, bool):
                raise ValueError(f"{key} must be a number")
            try:
                value = float(raw_value)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f"{key} must be a number") from error
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{key} must be between {lower:g} and {upper:g}")
            return value

        effective_parameters = {
            "period_seconds": read_number("period_seconds", 0.2, 10.0),
            "expand_seconds": read_number("expand_seconds", 0.02, 5.0),
            "collapse_seconds": read_number("collapse_seconds", 0.02, 5.0),
            "sphere_radius_fraction": read_number("sphere_radius_fraction", 0.05, 1.0),
            "base_glow": read_number("base_glow", 0.0, 1.0),
            "peak_glow": read_number("peak_glow", 0.0, 1.0),
        }
        if (
            effective_parameters["expand_seconds"] + effective_parameters["collapse_seconds"]
            > effective_parameters["period_seconds"]
        ):
            raise ValueError("expand_seconds + collapse_seconds must not exceed period_seconds")
        if effective_parameters["base_glow"] > effective_parameters["peak_glow"]:
            raise ValueError("base_glow must not exceed peak_glow")
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, _delta):
        phase = self.elapsed % self.period
        if phase < self.expand:
            beat = _smooth(phase / self.expand)
        elif phase < self.expand + self.collapse:
            beat = 1 - _smooth((phase - self.expand) / self.collapse)
        else:
            beat = 0.0

        radius = self.base_radius * (1 + beat)
        edge = radius * self.EDGE_SOFTNESS
        glow = self.base_glow + (self.peak_glow - self.base_glow) * beat
        frame = []
        for point in self.positions:
            overshoot = _distance(point, self.center) - radius
            sphere = 1.0 if overshoot <= 0 else max(0.0, 1 - overshoot / edge)
            frame.append((round(255 * max(sphere, glow)), 0, 0))
        return frame
