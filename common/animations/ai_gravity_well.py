import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class GravityWell(SpatialAnimation):
    name = "ai_gravity_well"
    author = "Carlos Gil & AI"
    description = "A moving 3D well bends color bands into a swirling spiral."

    def _initialise_effect(self, _parameters):
        self.phase = self.generator.uniform(0, 2 * math.pi)
        self.hue = self.generator.random()

    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            dx = x - self.tree_radius * 0.35 * math.sin(self.elapsed * 0.19 + self.phase)
            dy = y - self.tree_radius * 0.35 * math.cos(self.elapsed * 0.16 + self.phase)
            dz = z - self.height * (0.5 + 0.3 * math.sin(self.elapsed * 0.13))
            radius = math.sqrt(dx * dx + dy * dy + dz * dz)
            angle = math.atan2(dy, dx)
            warped = radius * 7 - angle * 2 + self.elapsed * 0.4
            intensity = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(warped)) ** 3
            frame.append(tuple(round(channel * intensity) for channel in _rgb(self.hue + warped * 0.025, 0.9, 1)))
        return frame
