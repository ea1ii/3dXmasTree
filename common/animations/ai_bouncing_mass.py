import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class BouncingMass(SpatialAnimation):
    name = "ai_bouncing_mass"
    author = "Carlos Gil & AI"
    description = "A gravity-driven luminous mass bounces with diminishing restitution."

    def _initialise_effect(self, _parameters):
        self.radius = max(self.tree_radius * 0.12, 0.025)
        self.gravity = 2.8 * self.height
        self.restitution = 0.78
        self.position = [0.0, 0.0, self.height * 0.85]
        self.velocity = [self.tree_radius * 0.3, 0.0, 0.0]
        self.color = _rgb(self.generator.uniform(0.04, 0.15), 0.9, 1)
        self.substep = 1 / 120

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            self.velocity[2] -= self.gravity * step
            for axis in range(3):
                self.position[axis] += self.velocity[axis] * step
            if self.position[2] < self.radius:
                self.position[2] = self.radius
                self.velocity[2] = abs(self.velocity[2]) * self.restitution
                if self.velocity[2] < self.height * 0.08:
                    self.velocity[2] = self.height * self.generator.uniform(0.35, 0.75)
                    self.velocity[0] = self.generator.uniform(-1, 1) * self.tree_radius
                    self.velocity[1] = self.generator.uniform(-1, 1) * self.tree_radius
            radial = math.hypot(self.position[0], self.position[1])
            if radial > self.tree_radius * 0.85:
                scale = self.tree_radius * 0.85 / max(radial, 1e-9)
                self.position[0] *= scale
                self.position[1] *= scale
                self.velocity[0] *= -0.75
                self.velocity[1] *= -0.75
            remaining -= step
        return [
            tuple(round(channel * max(0.0, 1 - _distance(point, self.position) / self.radius)) for channel in self.color)
            for point in self.positions
        ]