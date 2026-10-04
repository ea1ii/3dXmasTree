import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Afterimage(SpatialAnimation):
    name = "ai_afterimage"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "Three outer-tree travelers leave overlapping fading color echoes."

    def _initialise_effect(self, _parameters):
        self.trail = [0.0] * self.led_count
        self.hue = self.generator.random()
        self.width = max(self.tree_radius * 0.18, 0.045)
        self.travelers = [
            {
                "angle": self.generator.uniform(0.0, 2 * math.pi),
                "angular_speed": self.generator.choice((-1.0, 1.0)) * self.generator.uniform(0.18, 0.36),
                "height_phase": self.generator.uniform(0.0, 2 * math.pi),
                "height_speed": self.generator.uniform(0.22, 0.5),
                "radius_center": self.generator.uniform(0.58, 0.82),
                "radius_swing": self.generator.uniform(0.1, 0.18),
            }
            for _ in range(3)
        ]

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