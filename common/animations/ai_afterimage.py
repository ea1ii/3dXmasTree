import math
import random
from collections.abc import Mapping
from pathlib import Path

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Afterimage(SpatialAnimation):
    name = "ai_afterimage"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "A number of outer-tree travelers leave overlapping fading color echoes."

    TRAVELER_COUNT = 5
    ANGULAR_SPEED_RANGE = (0.18, 0.36)
    HEIGHT_SPEED_RANGE = (0.22, 1.5)
    RADIUS_CENTER_RANGE = (0.58, 0.82)
    RADIUS_SWING_RANGE = (0.1, 0.18)
    PARAMETER_DEFAULTS = {
        "traveler_count": 5,
        "angular_speed_range": (0.18, 0.36),
        "height_speed_range": (0.22, 1.5),
    }
    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(
        self,
        parameters: Mapping[str, object],
    ) -> None:
        effect_parameters = self._load_effect_parameters(parameters, self.name)
        self.traveler_count = effect_parameters["traveler_count"]
        self.angular_speed_range = effect_parameters["angular_speed_range"]
        self.height_speed_range = effect_parameters["height_speed_range"]

        self.generator = random.Random()
        self.trail = [0.0] * self.led_count
        self.hue = self.generator.random()
        self.width = max(self.tree_radius * 0.18, 0.045)
        self.travelers = [
            {
                "angle": self.generator.uniform(0.0, 2 * math.pi),
                "angular_speed": self.generator.choice((-1.0, 1.0)) * self.generator.uniform(*self.angular_speed_range),
                "height_phase": self.generator.uniform(0.0, 2 * math.pi),
                "height_speed": self.generator.uniform(*self.height_speed_range),
                "radius_center": self.generator.uniform(*self.RADIUS_CENTER_RANGE),
                "radius_swing": self.generator.uniform(*self.RADIUS_SWING_RANGE),
            }
            for _ in range(self.traveler_count)
        ]

    @classmethod
    def _load_effect_parameters(cls, parameters, effect_name):
        configured = super()._merge_effect_parameters(
            parameters,
            effect_name,
            cls.PARAMETER_DEFAULTS,
            cls.PARAMETER_SIDECAR,
        )

        raw_traveler_count = configured["traveler_count"]
        if isinstance(raw_traveler_count, bool):
            raise ValueError("traveler_count must be a positive integer")
        try:
            traveler_count = int(raw_traveler_count)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("traveler_count must be a positive integer") from error
        if traveler_count < 1 or traveler_count != raw_traveler_count:
            raise ValueError("traveler_count must be a positive integer")

        angular_speed_range = cls._read_range(
            configured["angular_speed_range"],
            "angular_speed_range",
            0.05,
            0.60,
            minimum_exclusive=True,
        )

        height_speed_range = cls._read_range(
            configured["height_speed_range"],
            "height_speed_range",
            0.05,
            2.0,
            minimum_exclusive=True,
        )

        radius_center_range = cls._read_range(
            configured["radius_center_range"],
            "radius_center_range",
            0.01,
            1.0,
            minimum_exclusive=True,
        )

        radius_swing_range = cls._read_range(
            configured["radius_swing_range"],
            "radius_swing_range",
            0.01,
            0.5,
            minimum_exclusive=True,
        )


        effective_parameters = {
            "traveler_count": traveler_count,
            "angular_speed_range": angular_speed_range,
            "height_speed_range": height_speed_range,
            "radius_center_range": radius_center_range,
            "radius_swing_range": radius_swing_range
        }
        cls._persist_effect_parameters(effective_parameters)    
        return effective_parameters

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta):
        fade = math.exp(-delta * 0.15)
        self.trail = [value * fade for value in self.trail]
        for traveler in self.travelers:
            angle = traveler["angle"] + self.elapsed * traveler["angular_speed"]
            radial_fraction = traveler["radius_center"] + traveler["radius_swing"] * math.sin(
                self.elapsed * 0.65 + traveler["height_phase"]
            )
            center = (
                self.tree_radius * radial_fraction * math.cos(angle),
                self.tree_radius * radial_fraction * math.sin(angle),
                self.height * (0.08 + 0.84 * (0.5 + 0.5 * math.sin(
                    self.elapsed * traveler["height_speed"] + traveler["height_phase"]
                ))),
            )
            for index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, center) / self.width) ** 2)
                self.trail[index] = max(self.trail[index], glow)
        color = _rgb(self.hue, 0.88, 1)
        return [tuple(round(channel * intensity) for channel in color) for intensity in self.trail]