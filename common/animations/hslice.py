import colorsys
import json
import math
import random
from collections.abc import Mapping
from pathlib import Path

from common.animations import Animation, LEDFrame


class HorizontalSliceAnimation(Animation):
    name = "hslice"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "A bouncing horizontal plane divides two changing contrasting hues."

    HUE_SEPARATION_RANGE = (1 / 3, 0.5)
    HALF_SWEEP_SECONDS_RANGE = (1.0, 5.0)
    PARAMETER_DEFAULTS = {
        "hue_separation_range": HUE_SEPARATION_RANGE,
        "half_sweep_seconds_range": HALF_SWEEP_SECONDS_RANGE,
        "saturation": 0.92,
        "value": 1.0,
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
        self.hue_separation_range = effect_parameters["hue_separation_range"]
        self.half_sweep_seconds_range = effect_parameters["half_sweep_seconds_range"]
        self.saturation = effect_parameters["saturation"]
        self.value = effect_parameters["value"]
        self.led_count = led_count
        self.generator = random.Random()
        self.positions = self._read_positions(parameters.get("positions"), led_count)
        self.minimum_z = min(position[2] for position in self.positions)
        self.maximum_z = max(position[2] for position in self.positions)
        self.height = self.maximum_z - self.minimum_z
        if self.height <= 0:
            self.height = 1.0
            self.maximum_z = self.minimum_z + self.height

        margin = self.height * 0.001
        self.bottom = self.minimum_z - margin
        self.top = self.maximum_z + margin
        self.plane_z = self.top
        self.direction = -1.0
        self.speed = self._random_speed()
        self.below_hue = self.generator.random()
        self.above_hue = self._contrasting_hue(self.below_hue)
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
            raise ValueError(f"Invalid hslice parameter sidecar: {error}") from error
        if not isinstance(sidecar_parameters, dict):
            raise ValueError("hslice parameter sidecar must contain a JSON object")

        overrides = parameters.get("hslice", {})
        if not isinstance(overrides, Mapping):
            raise ValueError("parameters['hslice'] must be a mapping")
        configured = {**cls.PARAMETER_DEFAULTS, **sidecar_parameters, **overrides}

        hue_separation_range = cls._read_range(
            configured["hue_separation_range"],
            "hue_separation_range",
            0.0,
            0.5,
            minimum_exclusive=True,
        )
        half_sweep_seconds_range = cls._read_range(
            configured["half_sweep_seconds_range"],
            "half_sweep_seconds_range",
            0.0,
            math.inf,
            minimum_exclusive=True,
        )
        saturation = cls._read_unit_interval(configured["saturation"], "saturation")
        value = cls._read_unit_interval(configured["value"], "value")
        effective_parameters = {
            "hue_separation_range": hue_separation_range,
            "half_sweep_seconds_range": half_sweep_seconds_range,
            "saturation": saturation,
            "value": value,
        }
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters
    def _contrasting_hue(self, reference_hue):
        separation = self.generator.uniform(*self.hue_separation_range)
        direction = self.generator.choice((-1.0, 1.0))
        return (reference_hue + direction * separation) % 1.0

    def _hue_color(self, hue):
        return tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue, self.saturation, self.value)
        )

    def _random_speed(self):
        return self.height / self.generator.uniform(*self.half_sweep_seconds_range)

    def _bounce(self):
        if self.direction < 0:
            self.below_hue = self._contrasting_hue(self.above_hue)
        else:
            self.above_hue = self._contrasting_hue(self.below_hue)
        self.direction *= -1.0
        self.speed = self._random_speed()

    def _advance_plane(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            boundary = self.bottom if self.direction < 0 else self.top
            distance = abs(boundary - self.plane_z)
            time_to_boundary = distance / self.speed
            if remaining < time_to_boundary:
                self.plane_z += self.direction * self.speed * remaining
                return

            self.plane_z = boundary
            remaining -= time_to_boundary
            self._bounce()

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_plane(delta_seconds)
        below_color = self._hue_color(self.below_hue)
        above_color = self._hue_color(self.above_hue)
        return [
            above_color if z >= self.plane_z else below_color
            for _x, _y, z in self.positions
        ]

