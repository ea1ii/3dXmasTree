import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Pendulum(SpatialAnimation):
    name = "ai_pendulum"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "A bright beam swings through the tree like a weighted pendulum."

    def _initialise_effect(self, _parameters):
        self.amplitude = self.generator.uniform(0.55, 0.95)
        self.rate = self.generator.uniform(0.35, 0.65)
        self.phase = self.generator.random() * 2 * math.pi
        self.color = _rgb(self.generator.uniform(0.08, 0.16), 0.75, 1)
        self.width = max(self.tree_radius * 0.4, 0.08)
        self.bob_radius = max(self.tree_radius * 0.24, 0.05)

    def _render_frame(self, _delta):
        angle = self.amplitude * math.sin(self.elapsed * self.rate + self.phase)
        end = (self.tree_radius * math.sin(angle), 0.0, self.height * (0.58 + 0.32 * math.cos(angle)))
        frame = []
        for point in self.positions:
            line = (end[0], end[1], end[2])
            length_squared = sum(value * value for value in line)
            projection = max(0.0, min(1.0, sum(a * b for a, b in zip(point, line)) / max(length_squared, 1e-9)))
            closest = tuple(projection * value for value in line)
            glow = max(0.0, 1 - _distance(point, closest) / self.width)
            glow = max(glow, max(0.0, 1 - _distance(point, end) / self.bob_radius))
            frame.append(tuple(round(channel * glow) for channel in self.color))
        return frame