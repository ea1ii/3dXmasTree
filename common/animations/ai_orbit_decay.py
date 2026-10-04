import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class OrbitDecay(SpatialAnimation):
    name = "ai_orbit_decay"
    author = "Carlos Gil & AI"
    description = "A particle spirals inward under gravity and gradual orbital drag."

    def _initialise_effect(self, _parameters):
        self.radius_limit = max(self.tree_radius * 0.85, 0.08)
        self.particle_radius = max(self.tree_radius * 0.07, 0.018)
        orbit_radius = self.radius_limit * 0.78
        self.mu = self.generator.uniform(0.35, 0.7) * orbit_radius ** 3
        self.position = [orbit_radius, 0.0, self.height * 0.55]
        circular_speed = math.sqrt(self.mu / orbit_radius)
        self.velocity = [0.0, circular_speed * self.generator.uniform(0.78, 1.12), 0.0]
        self.drag = self.generator.uniform(0.012, 0.035)
        self.color = _rgb(self.generator.random(), 0.85, 1)

    def _acceleration(self, position):
        radius_squared = sum(value * value for value in position)
        radius = max(math.sqrt(radius_squared), 1e-5)
        factor = -self.mu / (radius_squared * radius)
        return [factor * value for value in position]

    def _render_frame(self, delta):
        steps = max(1, min(12, math.ceil(delta / 0.02)))
        step = delta / steps
        for _ in range(steps):
            acceleration = self._acceleration(self.position)
            self.position = [self.position[axis] + self.velocity[axis] * step + 0.5 * acceleration[axis] * step * step for axis in range(3)]
            next_acceleration = self._acceleration(self.position)
            self.velocity = [
                (self.velocity[axis] + 0.5 * (acceleration[axis] + next_acceleration[axis]) * step)
                * math.exp(-self.drag * step)
                for axis in range(3)
            ]
            radius = math.sqrt(sum(value * value for value in self.position))
            if radius > self.radius_limit:
                normal = [value / radius for value in self.position]
                self.position = [normal[axis] * self.radius_limit for axis in range(3)]
                outward = sum(self.velocity[axis] * normal[axis] for axis in range(3))
                if outward > 0:
                    self.velocity = [self.velocity[axis] - 1.7 * outward * normal[axis] for axis in range(3)]
            if radius < self.particle_radius * 1.5:
                self.position = [self.radius_limit * 0.78, 0.0, self.height * 0.55]
                speed = math.sqrt(self.mu / max(self.radius_limit * 0.78, 1e-4))
                self.velocity = [0.0, speed, 0.0]
        return [
            tuple(round(channel * max(0.0, 1 - _distance(point, self.position) / self.particle_radius)) for channel in self.color)
            for point in self.positions
        ]