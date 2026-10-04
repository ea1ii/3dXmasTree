import math

from common.animations.ai_base import SpatialAnimation, _rgb


class GravityFlip(SpatialAnimation):
    name = "ai_gravity_flip"
    author = "Carlos Gil & AI"
    description = "Color bands stream up or down as gravity repeatedly reverses."

    def _initialise_effect(self, _parameters):
        self.direction = self.generator.choice((-1.0, 1.0))
        self.flip_remaining = self.generator.uniform(2.0, 5.0)
        self.speed = self.generator.uniform(0.18, 0.35)
        self.hue = self.generator.random()

    def _render_frame(self, delta):
        self.flip_remaining -= delta
        if self.flip_remaining <= 0:
            self.direction *= -1
            self.flip_remaining = self.generator.uniform(2.0, 5.0)
        frame = []
        for _x, _y, z in self.positions:
            flow = self.direction * z - self.elapsed * self.speed
            pulse = max(0.0, math.sin(2 * math.pi * (flow * 2.5 % 1))) ** 2
            frame.append(tuple(round(channel * (0.12 + 0.88 * pulse)) for channel in _rgb(self.hue + z * 0.12, 0.85, 1)))
        return frame