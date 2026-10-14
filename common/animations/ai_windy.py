import colorsys
import math
from collections.abc import Mapping
from pathlib import Path

from common.animations.ai_base import SpatialAnimation

TWO_PI = 2 * math.pi
GREEN_HUE = 0.33
SPARK_COLOR = (190, 220, 255)


class Windy(SpatialAnimation):
    name = "ai_windy"
    author = "Carlos Gil & AI"
    version = "0.1.0"
    description = "A dark green plane sweeps around the tree leaving a fading trail, with cool white sparks."

    PARAMETER_DEFAULTS = {
        "rotation_seconds": 24.0,
        "plane_width_degrees": 18,
        "plane_brightness": 0.55,
        "trail_brightness": 0.2,
        "sparks_per_second": 5,
        "spark_rise_seconds": 0.08,
        "spark_fade_seconds_range": (1.5, 4.0),
    }
    PARAMETER_SIDECAR = Path(__file__).with_suffix(".json")

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(self, parameters: Mapping[str, object]) -> None:
        effect_parameters = self._load_effect_parameters(parameters, self.name)
        self.angular_speed = TWO_PI / effect_parameters["rotation_seconds"]
        self.plane_width = math.radians(effect_parameters["plane_width_degrees"])
        self.plane_color = self._green(effect_parameters["plane_brightness"])
        self.trail_color = self._green(effect_parameters["trail_brightness"])
        self.spark_rate = effect_parameters["sparks_per_second"]
        self.spark_rise = effect_parameters["spark_rise_seconds"]
        self.spark_fade_range = effect_parameters["spark_fade_seconds_range"]
        self.start_angle = self.generator.uniform(0, TWO_PI)
        self.point_angles = [math.atan2(y, x) for x, y, _z in self.positions]
        self.sparks = []
        self.spark_budget = 0.0

    @staticmethod
    def _green(brightness):
        return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(GREEN_HUE, 1.0, brightness))

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
            "rotation_seconds": read_number("rotation_seconds", 2.0, 600.0),
            "plane_width_degrees": read_number("plane_width_degrees", 2.0, 90.0),
            "plane_brightness": read_number("plane_brightness", 0.05, 1.0),
            "trail_brightness": read_number("trail_brightness", 0.0, 1.0),
            "sparks_per_second": read_number("sparks_per_second", 0.0, 100.0),
            "spark_rise_seconds": read_number("spark_rise_seconds", 0.01, 2.0),
            "spark_fade_seconds_range": cls._read_range(
                configured["spark_fade_seconds_range"],
                "spark_fade_seconds_range",
                0.1,
                30.0,
            ),
        }
        if effective_parameters["trail_brightness"] > effective_parameters["plane_brightness"]:
            raise ValueError("trail_brightness must not exceed plane_brightness")
        cls._persist_effect_parameters(effective_parameters)
        return effective_parameters

    def _update_sparks(self, delta):
        self.spark_budget += delta * self.spark_rate
        while self.spark_budget >= 1.0:
            self.spark_budget -= 1.0
            self.sparks.append(
                {
                    "index": self.generator.randrange(self.led_count),
                    "age": 0.0,
                    "fade": self.generator.uniform(*self.spark_fade_range),
                }
            )
        for spark in self.sparks:
            spark["age"] += delta
        self.sparks = [
            spark for spark in self.sparks if spark["age"] < self.spark_rise + spark["fade"]
        ]

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta):
        plane_angle = self.start_angle + self.elapsed * self.angular_speed
        frame = []
        for angle in self.point_angles:
            behind = (plane_angle - angle) % TWO_PI
            wrapped = behind if behind <= math.pi else behind - TWO_PI
            plane = max(0.0, 1 - abs(wrapped) / self.plane_width)
            trail = (1 - behind / TWO_PI) ** 2
            frame.append(
                tuple(
                    round(max(p * plane, t * trail))
                    for p, t in zip(self.plane_color, self.trail_color)
                )
            )

        self._update_sparks(delta)
        for spark in self.sparks:
            if spark["age"] < self.spark_rise:
                level = spark["age"] / self.spark_rise
            else:
                level = 1 - (spark["age"] - self.spark_rise) / spark["fade"]
            frame[spark["index"]] = tuple(
                max(base, round(channel * level))
                for base, channel in zip(frame[spark["index"]], SPARK_COLOR)
            )
        return frame
