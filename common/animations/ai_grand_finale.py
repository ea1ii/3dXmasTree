import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class GrandFinale(SpatialAnimation):
    name = "ai_grand_finale"
    author = "Carlos Gil & AI"
    description = "A staged build of waves, bursts, and a sustained all-tree finale."
    duration_seconds = 36.0

    def _initialise_effect(self, _parameters):
        self.color = _rgb(self.generator.uniform(0.0, 1.0), 0.85, 1)
        self.center = (
            self.generator.uniform(-self.tree_radius * 0.3, self.tree_radius * 0.3),
            self.generator.uniform(-self.tree_radius * 0.3, self.tree_radius * 0.3),
            self.height * 0.5,
        )
        self.max_distance = max(_distance(point, self.center) for point in self.positions)

    def _render_frame(self, _delta):
        if self.elapsed >= self.duration_seconds * 0.82:
            return [(255, 255, 255)] * self.led_count
        if self.elapsed < 9:
            front = self.elapsed / 9
            return [
                self.color if z <= front * self.height else (0, 0, 0)
                for _x, _y, z in self.positions
            ]
        if self.elapsed < 23:
            front = ((self.elapsed - 9) / 14) * self.max_distance
            return [
                self.color if _distance(point, self.center) <= front else (0, 0, 0)
                for point in self.positions
            ]
        pulse = max(0.0, math.sin((self.elapsed - 23) * 2.8)) ** 5
        return [tuple(round(channel * (0.25 + 0.75 * pulse)) for channel in self.color) for _ in self.positions]
