import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class FrostBloom(SpatialAnimation):
    name = "ai_frost_bloom"
    author = "Carlos Gil & AI"
    description = "Cold-white branches spread from the base and retreat like growing frost."

    def _initialise_effect(self, _parameters):
        self.cycle = self.generator.uniform(7.0, 11.0)
        self.branch_angles = [
            2 * math.pi * index / 9 + self.generator.uniform(-0.18, 0.18)
            for index in range(9)
        ]

    def _render_frame(self, _delta):
        progress = (self.elapsed % self.cycle) / self.cycle
        growth = 1 - abs(2 * progress - 1)
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x)
            branch_distance = min(
                abs((angle - branch + math.pi) % (2 * math.pi) - math.pi)
                for branch in self.branch_angles
            )
            reach = growth * (0.35 + 0.8 * z)
            near_branch = math.exp(-(branch_distance / 0.17) ** 2)
            intensity = near_branch * _smooth((reach - math.hypot(x, y)) / 0.08)
            frame.append(tuple(round(channel * intensity) for channel in (195, 235, 255)))
        return frame
