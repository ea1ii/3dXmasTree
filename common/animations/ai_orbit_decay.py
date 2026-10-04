import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class OrbitDecay(SpatialAnimation):
    name = "ai_orbit_decay"
    author = "Carlos Gil & AI"
    version = "0.1.3"
    description = "A particle spirals inward under gravity and gradual orbital drag."

    def _initialise_effect(self, _parameters):
        self.radius_limit = max(self.tree_radius * 0.85, 0.08)
        self.particle_radius = max(self.tree_radius * 0.72, 0.14)
        self.center = (0.0, 0.0, self.height * 0.5)
        orbit_radius = self.radius_limit * 0.68
        self.mu = self.generator.uniform(0.35, 0.7) * orbit_radius ** 3
        self.position = [self.center[0] + orbit_radius, self.center[1], self.center[2]]
        circular_speed = math.sqrt(self.mu / orbit_radius)
        self.velocity = [0.0, circular_speed * self.generator.uniform(0.78, 1.12), 0.0]
        self.drag = self.generator.uniform(0.012, 0.035)
        self.color = _rgb(self.generator.random(), 0.85, 1)
        self.trail = [0.0] * self.led_count

    def _acceleration(self, position):
        relative = [position[axis] - self.center[axis] for axis in range(3)]
        radius_squared = sum(value * value for value in relative)
        radius = max(math.sqrt(radius_squared), 1e-5)
        factor = -self.mu / (radius_squared * radius)
        return [factor * value for value in relative]

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
            relative_position = [self.position[axis] - self.center[axis] for axis in range(3)]
            radius = math.sqrt(sum(value * value for value in relative_position))
            if radius > self.radius_limit:
                normal = [value / radius for value in relative_position]
                self.position = [
                    self.center[axis] + normal[axis] * self.radius_limit
                    for axis in range(3)
                ]
                outward = sum(self.velocity[axis] * normal[axis] for axis in range(3))
                if outward > 0:
                    self.velocity = [self.velocity[axis] - 1.7 * outward * normal[axis] for axis in range(3)]
            if radius < self.particle_radius * 1.5:
                self.position = [self.center[0] + self.radius_limit * 0.68, self.center[1], self.center[2]]
                speed = math.sqrt(self.mu / max(self.radius_limit * 0.78, 1e-4))
                self.velocity = [0.0, speed, 0.0]
        self.trail = [level * math.exp(-delta * 1.1) for level in self.trail]
        for index, point in enumerate(self.positions):
            glow = max(0.0, 1 - _distance(point, self.position) / self.particle_radius)
            self.trail[index] = max(self.trail[index], glow)
        return [tuple(round(channel * level) for channel in self.color) for level in self.trail]