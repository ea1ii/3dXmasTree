import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class ChromaticHelix(SpatialAnimation):
    name = "ai_chromatic_helix"
    author = "Carlos Gil & AI"
    description = "A vivid rainbow helix winds upward and rotates around the tree."

    def _initialise_effect(self, _parameters):
        self.speed = self.generator.uniform(0.08, 0.18)
        self.turns = self.generator.uniform(1.5, 3.0)

    def _render_frame(self, _delta):
        return [
            _rgb(math.atan2(y, x) / (2 * math.pi) + z * self.turns - self.elapsed * self.speed, 1, 1)
            for x, y, z in self.positions
        ]
