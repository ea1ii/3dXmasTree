import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class LuminousTide(SpatialAnimation):
    name = "ai_luminous_tide"
    author = "Carlos Gil & AI"
    description = "A turquoise ring tide circles and rises through the tree."

    def _initialise_effect(self, _parameters):
        self.speed = self.generator.uniform(0.14, 0.25)
        self.hue = self.generator.uniform(0.48, 0.56)

    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            radial = math.hypot(x, y) / max(self.tree_radius, 1e-6)
            phase = radial * 2.4 + z * 1.6 - self.elapsed * self.speed
            band = math.exp(-((math.sin(phase) / 0.28) ** 2))
            shimmer = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(math.atan2(y, x) * 4 + self.elapsed))
            frame.append(tuple(round(channel * band * shimmer) for channel in _rgb(self.hue, 0.8, 1)))
        return frame
