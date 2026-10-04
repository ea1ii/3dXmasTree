import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class RibbonKnot(SpatialAnimation):
    name = "ai_ribbon_knot"
    author = "Carlos Gil & AI"
    description = "Two bright colored ribbons braid around the tree in a moving knot."

    def _initialise_effect(self, _parameters):
        self.turns = self.generator.uniform(1.5, 2.8)
        self.speed = self.generator.uniform(0.1, 0.2)
        self.width = max(self.tree_radius * 0.12, 0.025)
        self.phase = self.generator.random() * 2 * math.pi
        self.colors = (_rgb(0.9, 0.95, 1), _rgb(0.53, 0.9, 1))

    def _render_frame(self, _delta):
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x)
            base = self.turns * 2 * math.pi * z + self.elapsed * self.speed + self.phase
            radius = self.tree_radius * (0.88 - 0.68 * z)
            error_a = abs((angle - base + math.pi) % (2 * math.pi) - math.pi)
            error_b = abs((angle - base - math.pi + math.pi) % (2 * math.pi) - math.pi)
            near_a = abs(math.hypot(x, y) - radius) < self.width and error_a < 0.5
            near_b = abs(math.hypot(x, y) - radius) < self.width and error_b < 0.5
            frame.append(self.colors[0] if near_a else self.colors[1] if near_b else (0, 0, 0))
        return frame