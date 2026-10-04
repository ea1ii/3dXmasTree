import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class Shockwave(SpatialAnimation):
    name = "ai_shockwave"
    author = "Carlos Gil & AI"
    description = "A bright spherical shell expands from random points through the tree."

    def _initialise_effect(self, _parameters):
        self.cycle = 0.0
        self.duration = self.generator.uniform(3.0, 6.0)
        self._new_center()

    def _new_center(self):
        self.center = (
            self.generator.uniform(-self.tree_radius * 0.35, self.tree_radius * 0.35),
            self.generator.uniform(-self.tree_radius * 0.35, self.tree_radius * 0.35),
            self.generator.uniform(0, self.height),
        )
        self.max_distance = max(_distance(point, self.center) for point in self.positions)
        self.color = _rgb(self.generator.random(), 0.92, 1)

    def _render_frame(self, delta):
        self.cycle += delta
        if self.cycle >= self.duration:
            self.cycle %= self.duration
            self.duration = self.generator.uniform(3.0, 6.0)
            self._new_center()
        front = self.max_distance * self.cycle / self.duration
        width = max(self.max_distance * 0.045, 1e-4)
        return [
            tuple(round(channel * math.exp(-((_distance(point, self.center) - front) / width) ** 2)) for channel in self.color)
            for point in self.positions
        ]
