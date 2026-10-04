import math

from common.animations.ai_base import SpatialAnimation, _rgb


class BraidedTwins(SpatialAnimation):
    name = "ai_braided_twins"
    author = "Carlos Gil & AI"
    description = "Two colored climbing trails weave around each other."

    def _initialise_effect(self, _parameters):
        self.turns = self.generator.uniform(2.0, 3.5)
        self.rate = self.generator.uniform(0.12, 0.25)
        self.width = max(self.tree_radius * 0.14, 0.035)
        self.colors = (_rgb(0.99, 0.9, 1), _rgb(0.56, 0.9, 1))

    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x)
            expected = self.turns * 2 * math.pi * z + self.elapsed * self.rate
            phase_error = abs((angle - expected + math.pi) % (2 * math.pi) - math.pi)
            opposite_error = abs((angle - expected - math.pi + math.pi) % (2 * math.pi) - math.pi)
            radius = math.hypot(x, y)
            target_radius = self.tree_radius * (0.92 - 0.72 * z)
            near_tube = abs(radius - target_radius) < self.width
            if near_tube and phase_error < 0.48:
                frame.append(self.colors[0])
            elif near_tube and opposite_error < 0.48:
                frame.append(self.colors[1])
            else:
                frame.append((0, 0, 0))
        return frame