import math

from common.animations.ai_base import SpatialAnimation, _mix


class TideClock(SpatialAnimation):
    name = "ai_tide_clock"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "A rotating day-night terminator divides warm and cool halves."

    def _initialise_effect(self, _parameters):
        self.angle = self.generator.uniform(0, 2 * math.pi)
        self.speed = self.generator.choice((-1, 1)) * self.generator.uniform(0.5, 0.95)
        self.day = (255, 112, 30)
        self.night = (20, 65, 190)
        self.edge = (220, 245, 255)

    def _render_frame(self, _delta):
        angle = self.angle + self.elapsed * self.speed
        nx, ny = math.cos(angle), math.sin(angle)
        frame = []
        for x, y, z in self.positions:
            side = x * nx + y * ny + self.tree_radius * 0.24 * math.sin(z * 8 - self.elapsed * 0.8)
            edge = math.exp(-abs(side) / max(self.tree_radius * 0.18, 0.025))
            field = self.day if side >= 0 else self.night
            frame.append(_mix(field, self.edge, edge * 0.85))
        return frame