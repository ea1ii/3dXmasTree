import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Afterimage(SpatialAnimation):
    name = "ai_afterimage"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "A bright 3D traveler leaves a slowly fading color echo."

    def _initialise_effect(self, _parameters):
        self.trail = [0.0] * self.led_count
        self.hue = self.generator.random()
        self.speed = self.generator.uniform(0.2, 0.38)
        self.width = max(self.tree_radius * 0.25, 0.06)

    def _render_frame(self, delta):
        fade = math.exp(-delta * 0.22)
        self.trail = [value * fade for value in self.trail]
        phase = (self.elapsed * self.speed) % 1.0
        center = (
            self.tree_radius * 0.8 * math.sin(phase * 2 * math.pi),
            self.tree_radius * 0.55 * math.sin(phase * 4 * math.pi),
            phase * self.height,
        )
        for index, point in enumerate(self.positions):
            glow = math.exp(-(_distance(point, center) / self.width) ** 2)
            self.trail[index] = max(self.trail[index], glow)
        color = _rgb(self.hue, 0.88, 1)
        return [tuple(round(channel * intensity) for channel in color) for intensity in self.trail]