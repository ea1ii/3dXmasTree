import math
from pathlib import Path
from typing import Any, Mapping

from common.animations.ai_base import SpatialAnimation, _rgb

class BouncingDisk(SpatialAnimation):
    name = "ai_bouncing_disk"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "A spring-launched colored disk rises, pauses, then falls and bounces."

    MASS_RANGE = (0.6, 1.8)
    GRAVITY_RANGE = (1.3, 2.7)
    INVISIBLE_FORCE_RANGE = (2.5, 5.0)
    RESTITUTION_RANGE = (0.65, 0.85)
    BOUNCE_THRESHOLD_RANGE = (0.025, 0.06)
    PARAMETER_DEFAULTS = {
        "mass_range": MASS_RANGE,
        "gravity_range": GRAVITY_RANGE,
        "invisible_force_range": INVISIBLE_FORCE_RANGE,
        "restitution_range": RESTITUTION_RANGE,
        "bounce_threshold_range": BOUNCE_THRESHOLD_RANGE,
    }
    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    def _initialise_effect(
            self, 
            parameters: Mapping[str, object],
    ):
        effect_parameters = self._load_effect_parameters(parameters, self.name)
        self.mass_range = effect_parameters["mass_range"]
        self.gravity_range = effect_parameters["gravity_range"]
        self.invisible_force_range = effect_parameters["invisible_force_range"]
        self.restitution_range = effect_parameters["restitution_range"]
        self.bounce_threshold_range = effect_parameters["bounce_threshold_range"]

        self.substep = 1 / 120
        self.disk_thickness = max(
            self.height * 0.085,
            self._estimate_led_spacing() * 1.5,
        )
        self.bottom_z = self.disk_thickness
        self.top_z = max(self.bottom_z, self.height - self.disk_thickness)
        self._start_cycle()

    @classmethod
    def _load_effect_parameters(cls, parameters, effect_name) -> dict[str, Any]:
        configured = super()._merge_effect_parameters(
            parameters,
            effect_name,
            cls.PARAMETER_DEFAULTS,
            cls.PARAMETER_SIDECAR,
        )

        mass_range = cls._read_range(
            configured["mass_range"],
            "mass_range",
            0.0,
            5.0,
            minimum_exclusive=True,
        )

        gravity_range = cls._read_range(
            configured["gravity_range"],
            "gravity_range",
            0.0,
            10.0,
            minimum_exclusive=True,
        )
        invisible_force_range = cls._read_range(
            configured["invisible_force_range"],
            "invisible_force_range",
            0.0,
            10.0,
            minimum_exclusive=True,
        )
        restitution_range = cls._read_range(
            configured["restitution_range"],
            "restitution_range",
            0.0,
            1.0,
            minimum_exclusive=True,
        )
        bounce_threshold_range = cls._read_range(
            configured["bounce_threshold_range"],
            "bounce_threshold_range",
            0.0,
            1.0,
            minimum_exclusive=True,
        )

        effective_parameters = {
            "mass_range": mass_range,
            "gravity_range": gravity_range,
            "invisible_force_range": invisible_force_range,
            "restitution_range": restitution_range,
            "bounce_threshold_range": bounce_threshold_range,
        }
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters

    def _start_cycle(self):
        self.color = _rgb(self.generator.random(), 0.9, 1.0)
        self.mass = self.generator.uniform(*self.mass_range)
        self.gravity = self.height * self.generator.uniform(*self.gravity_range)
        self.compression_height = self.top_z - self.bottom_z
        self.invisible_force = self.mass * self.height * self.generator.uniform(*self.invisible_force_range)
        self.spring_stiffness = (
            2.0
            * self.invisible_force
            / self.compression_height
            * self.generator.uniform(0.98, 1.0)
        )
        self.spring_compression = 0.0
        self.restitution = self.generator.uniform(*self.restitution_range)
        self.bounce_threshold = self.height * self.generator.uniform(*self.bounce_threshold_range)
        self.position_z = self.bottom_z
        self.velocity_z = 0.0
        self.phase = "compressing"
        self.top_hold = 0.0

    def _advance_disk(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0.0:
            step = min(remaining, self.substep)
            if self.phase == "compressing":
                self.spring_compression = min(
                    self.compression_height,
                    max(0.0, self.position_z - self.bottom_z),
                )
                spring_force = self.spring_stiffness * self.spring_compression
                acceleration = (self.invisible_force - spring_force) / self.mass
                self.velocity_z += acceleration * step
                self.position_z += self.velocity_z * step
                if self.position_z >= self.top_z:
                    self.position_z = self.top_z
                    self.spring_compression = self.compression_height
                    self.velocity_z = 0.0
                    self.top_hold = self.generator.uniform(0.8, 2.0)
                    self.phase = "holding"
            elif self.phase == "holding":
                self.top_hold -= step
                if self.top_hold <= 0.0:
                    self.phase = "falling"
            else:
                self.velocity_z -= self.gravity * step
                self.position_z += self.velocity_z * step
                if self.position_z <= self.bottom_z:
                    self.position_z = self.bottom_z
                    self.velocity_z = abs(self.velocity_z) * self.restitution
                    if self.velocity_z <= self.bounce_threshold:
                        self._start_cycle()
            remaining -= step

    def _render_frame(self, delta_seconds):
        self._advance_disk(delta_seconds)
        frame = []
        width = max(self.disk_thickness, 1e-6)
        for _x, _y, z in self.positions:
            distance = abs(z - self.position_z) / width
            intensity = math.exp(-(distance * distance))
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame
