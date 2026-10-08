import json
import math
import random
from collections.abc import Mapping
from pathlib import Path

from common.animations import Animation, LEDFrame


class GaliciaAnimation(Animation):
    name = "galicia"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A thick cyan band sweeps through a cold-white 3D tree."

    COLD_WHITE = (210, 240, 255)
    CYAN = (0, 255, 255)
    SWEEP_DURATION_RANGE = (1.5, 4.0)
    PARAMETER_DEFAULTS = {
        "sweep_duration_range": SWEEP_DURATION_RANGE
    }
    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        effect_parameters = self._load_effect_parameters(parameters)
        self.sweep_duration_range = effect_parameters["sweep_duration_range"]
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

    @classmethod
    def _load_effect_parameters(cls, parameters):
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be a mapping")
        try:
            sidecar_parameters = json.loads(
                cls.PARAMETER_SIDECAR.read_text(encoding="utf-8")
            )
        except FileNotFoundError:
            sidecar_parameters = {}
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid galicia parameter sidecar: {error}") from error
        if not isinstance(sidecar_parameters, dict):
            raise ValueError("galicia parameter sidecar must contain a JSON object")

        overrides = parameters.get("galicia", {})
        if not isinstance(overrides, Mapping):
            raise ValueError("parameters['galicia'] must be a mapping")
        configured = {**cls.PARAMETER_DEFAULTS, **sidecar_parameters, **overrides}
        sweep_duration_range = cls._read_range(
            configured["sweep_duration_range"],
            "sweep_duration_range",
            0.0,
            math.inf,
            minimum_exclusive=True,
        )
        effective_parameters = {"sweep_duration_range": sweep_duration_range}
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters

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
        self.sweep_duration = self.generator.uniform(*self.sweep_duration_range)
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

