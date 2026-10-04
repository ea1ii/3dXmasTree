import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class MirrorChase(SpatialAnimation):
    name = "ai_mirror_chase"
    author = "Carlos Gil & AI"
    description = "Paired light waves race toward each other from opposite tree halves."

    def _initialise_effect(self, _parameters):
        self.period = self.generator.uniform(3.0, 5.0)
        self.phase = self.generator.random()
        self.colors = (_rgb(0.0, 1, 1), _rgb(0.57, 0.9, 1))

    def _render_frame(self, _delta):
        phase = (self.elapsed / self.period + self.phase) % 1.0
        left_front = phase
        right_front = 1 - phase
        frame = []
        for x, _y, z in self.positions:
            height = z / self.height
            if abs(height - left_front) < 0.06:
                frame.append(self.colors[0] if x < 0 else self.colors[1])
            elif abs(height - right_front) < 0.06:
                frame.append(self.colors[1] if x < 0 else self.colors[0])
            else:
                frame.append((0, 0, 0))
        return frame
