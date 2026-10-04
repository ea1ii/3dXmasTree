import math

from common.animations.ai_base import SpatialAnimation, _mix


class TideClock(SpatialAnimation):
    name = "ai_tide_clock"
    author = "Carlos Gil & AI"
    description = "A rotating day-night terminator divides warm and cool halves."

    def _initialise_effect(self, _parameters):
        self.angle = self.generator.uniform(0, 2 * math.pi)
        self.speed = self.generator.choice((-1, 1)) * self.generator.uniform(0.12, 0.3)
        self.day = (255, 112, 30)
        self.night = (20, 65, 190)
        self.edge = (220, 245, 255)

    def _render_frame(self, _delta):
        angle = self.angle + self.elapsed * self.speed
        nx, ny = math.cos(angle), math.sin(angle)
        frame = []
        for x, y, z in self.positions:
            side = x * nx + y * ny
            edge = math.exp(-abs(side) / max(self.tree_radius * 0.12, 0.02))
            field = self.day if side >= 0 else self.night
            frame.append(_mix(field, self.edge, edge * 0.85))
        return frame