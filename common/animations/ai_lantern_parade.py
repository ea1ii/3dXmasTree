import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class LanternParade(SpatialAnimation):
    name = "ai_lantern_parade"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Warm lantern groups orbit at staggered heights and gather apart."

    def _initialise_effect(self, _parameters):
        self.lanterns = [
            (self.generator.uniform(0, 2 * math.pi), self.generator.uniform(0.12, 0.3), self.generator.uniform(0.12, 0.88), _rgb(self.generator.uniform(0.055, 0.13), 0.62, 1))
            for _ in range(36)
        ]

    def _render_frame(self, _delta):
        frame = [(0, 0, 0)] * self.led_count
        for phase, speed, height, color in self.lanterns:
            angle = phase + self.elapsed * speed
            radius = self.tree_radius * (0.32 + 0.52 * (1 - height))
            center = (radius * math.cos(angle), radius * math.sin(angle), height * self.height)
            for index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, center) / max(self.tree_radius * 0.2, 0.045)) ** 2)
                if glow > 0.08:
                    frame[index] = tuple(round(channel * glow) for channel in color)
        return frame