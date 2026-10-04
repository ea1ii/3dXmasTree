import math

from common.animations.ai_base import SpatialAnimation, _rgb


class ElasticBranches(SpatialAnimation):
    name = "ai_elastic_branches"
    author = "Carlos Gil & AI"
    description = "A spring-linked tree flexes and settles under changing wind loads."

    def _initialise_effect(self, _parameters):
        self.nodes = [list(point) for point in self.positions]
        self.rest_lengths = {}
        for index, point in enumerate(self.positions):
            lower = [
                candidate
                for candidate in range(self.led_count)
                if self.positions[candidate][2] < point[2]
            ]
            if lower:
                parent = min(lower, key=lambda candidate: self.positions[candidate][2] - point[2] + 2 * math.dist(self.positions[candidate], point))
                self.rest_lengths[(parent, index)] = math.dist(self.positions[parent], point)
        self.velocities = [[0.0, 0.0, 0.0] for _ in self.positions]
        self.mass = 1.0
        self.spring = 18.0
        self.damping = 2.0
        self.wind_phase = self.generator.uniform(0, 2 * math.pi)
        self.color = _rgb(0.34, 0.8, 1)
        self.substep = 1 / 90

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            forces = [[0.0, 0.0, 0.0] for _ in self.nodes]
            wind = self.tree_radius * 0.12 * math.sin(self.elapsed * 0.9 + self.wind_phase)
            for (first, second), rest in self.rest_lengths.items():
                delta_vector = [self.nodes[second][axis] - self.nodes[first][axis] for axis in range(3)]
                distance = math.sqrt(sum(value * value for value in delta_vector))
                if distance <= 1e-9:
                    continue
                magnitude = self.spring * (distance - rest)
                for axis in range(3):
                    force = magnitude * delta_vector[axis] / distance
                    forces[first][axis] += force
                    forces[second][axis] -= force
            for index, point in enumerate(self.nodes):
                height_fraction = point[2] / max(self.height, 1e-6)
                forces[index][0] += wind * height_fraction
                forces[index][0] -= self.damping * self.velocities[index][0]
                for axis in range(3):
                    self.velocities[index][axis] += forces[index][axis] / self.mass * step
                    self.nodes[index][axis] += self.velocities[index][axis] * step
            remaining -= step
        return [
            tuple(round(channel * min(1.0, 0.25 + abs(self.nodes[index][0] - point[0]) * 3)) for channel in self.color)
            for index, point in enumerate(self.positions)
        ]