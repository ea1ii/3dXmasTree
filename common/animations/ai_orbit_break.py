import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class OrbitBreak(SpatialAnimation):
    name = "ai_orbit_break"
    author = "Carlos Gil & AI"
    description = "A ring of colored lights breaks into orbiting points and reforms."

    def _initialise_effect(self, _parameters):
        self.count = 12
        self.phase = self.generator.random() * 2 * math.pi
        self.period = self.generator.uniform(8.0, 12.0)
        self.colors = [_rgb(index / self.count, 0.9, 1) for index in range(self.count)]

    def _render_frame(self, _delta):
        cycle = (self.elapsed / self.period) % 1.0
        break_amount = abs(2 * cycle - 1)
        centers = []
        for index in range(self.count):
            angle = 2 * math.pi * index / self.count + self.phase + self.elapsed * 0.35
            radius = self.tree_radius * (0.5 + 0.42 * break_amount)
            height = self.height * (0.5 + 0.4 * break_amount * math.sin(angle * 2 + self.elapsed * 0.4))
            centers.append((radius * math.cos(angle), radius * math.sin(angle), height))
        frame = []
        for point in self.positions:
            intensity, color = 0.0, (0, 0, 0)
            for center, candidate in zip(centers, self.colors):
                glow = math.exp(-(_distance(point, center) / max(self.tree_radius * 0.16, 0.025)) ** 2)
                if glow > intensity:
                    intensity, color = glow, candidate
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame