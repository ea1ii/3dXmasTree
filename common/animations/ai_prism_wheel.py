import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class PrismWheel(SpatialAnimation):
    name = "ai_prism_wheel"
    author = "Carlos Gil & AI"
    description = "Rotating color wedges split the tree into a turning prism."

    def _initialise_effect(self, _parameters):
        self.speed = self.generator.choice((-1, 1)) * self.generator.uniform(0.04, 0.12)
        self.wedges = self.generator.randint(4, 8)
        self.offset = self.generator.random()

    def _render_frame(self, _delta):
        return [
            _rgb(math.floor(((math.atan2(y, x) / (2 * math.pi) + self.elapsed * self.speed + self.offset) % 1) * self.wedges) / self.wedges, 1, 1)
            for x, y, _z in self.positions
        ]
