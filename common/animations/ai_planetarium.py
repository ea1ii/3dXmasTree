import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Planetarium(SpatialAnimation):
    name = "ai_planetarium"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Small colored planets orbit amid a dim field of twinkling stars."

    def _initialise_effect(self, _parameters):
        self.stars = [self.generator.random() for _ in self.positions]
        self.planets = [
            (self.generator.uniform(0, 2 * math.pi), self.generator.uniform(0.12, 0.38), self.generator.uniform(0.25, 0.85), _rgb(self.generator.random(), 0.85, 1))
            for _ in range(10)
        ]

    def _render_frame(self, _delta):
        frame = []
        for index, point in enumerate(self.positions):
            star = self.stars[index]
            intensity = 0.2 + 0.65 * max(0.0, math.sin(self.elapsed * (0.75 + star) + star * 8)) ** 4
            color = tuple(round(channel * intensity) for channel in (110, 145, 255))
            for phase, rate, height, planet_color in self.planets:
                angle = phase + self.elapsed * rate
                radius = self.tree_radius * (0.35 + 0.25 * math.sin(phase))
                center = (radius * math.cos(angle), radius * math.sin(angle), height * self.height)
                glow = math.exp(-(_distance(point, center) / max(self.tree_radius * 0.28, 0.055)) ** 2)
                if glow > intensity:
                    color = tuple(round(channel * glow) for channel in planet_color)
                    intensity = glow
            frame.append(color)
        return frame