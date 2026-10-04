import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Dandelion(SpatialAnimation):
    name = "ai_dandelion"
    author = "Carlos Gil & AI"
    description = "Tiny colored seeds drift outward from a glowing center."

    def _initialise_effect(self, _parameters):
        self.center = (0.0, 0.0, self.height * 0.5)
        self.seeds = [
            (
                self.generator.uniform(-1, 1),
                self.generator.uniform(-1, 1),
                self.generator.uniform(-1, 1),
                self.generator.uniform(0.1, 1.0),
                _rgb(self.generator.random(), 0.8, 1),
                self.generator.random(),
            )
            for _ in range(24)
        ]

    def _render_frame(self, _delta):
        frame = [(0, 0, 0)] * self.led_count
        for dx, dy, dz, speed, color, phase in self.seeds:
            distance = (0.08 + ((self.elapsed * speed + phase) % 1.0) * 0.95) * self.tree_radius
            center = (
                dx * distance,
                dy * distance,
                self.center[2] + dz * distance,
            )
            fade = max(0.0, 1.0 - ((self.elapsed * speed + phase) % 1.0))
            for index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, center) / max(self.tree_radius * 0.055, 0.012)) ** 2) * fade
                if glow > 0.15:
                    frame[index] = tuple(round(channel * glow) for channel in color)
        return frame