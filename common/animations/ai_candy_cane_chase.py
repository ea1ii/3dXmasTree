import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class CandyCaneChase(SpatialAnimation):
    name = "ai_candy_cane_chase"
    author = "Carlos Gil & AI"
    description = "Red and white diagonal stripes spiral and chase up the tree."

    def _initialise_effect(self, _parameters):
        self.speed = self.generator.uniform(0.16, 0.32)
        self.twist = self.generator.uniform(2.5, 4.5)

    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x) / (2 * math.pi)
            stripe = math.sin(2 * math.pi * (angle * 3 + z * self.twist - self.elapsed * self.speed))
            frame.append((255, 20, 28) if stripe >= 0 else (248, 244, 230))
        return frame
