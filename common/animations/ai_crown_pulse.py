import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class CrownPulse(SpatialAnimation):
    name = "ai_crown_pulse"
    author = "Carlos Gil & AI"
    description = "Bright crown-born rings travel downward, then sweep back up."

    def _initialise_effect(self, _parameters):
        self.period = self.generator.uniform(4.0, 7.0)
        self.width = 0.045
        self.color = _rgb(self.generator.uniform(0.08, 0.16), 0.85, 1)

    def _render_frame(self, _delta):
        phase = (self.elapsed % self.period) / self.period
        position = 1 - abs(2 * phase - 1)
        return [
            tuple(round(channel * math.exp(-((z - position * self.height) / (self.width * self.height)) ** 2)) for channel in self.color)
            for _x, _y, z in self.positions
        ]
