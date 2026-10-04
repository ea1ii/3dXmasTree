import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class ElasticCollision(SpatialAnimation):
    name = "ai_elastic_collision"
    author = "Carlos Gil & AI"
    description = "Luminous spheres exchange momentum in elastic 3D collisions."

    def _initialise_effect(self, _parameters):
        self.radius = max(self.tree_radius * 0.1, 0.025)
        self.boundary = max(self.tree_radius * 0.9, 0.08)
        self.balls = []
        for index in range(4):
            angle = index * math.pi / 2
            position = [self.boundary * 0.45 * math.cos(angle), self.boundary * 0.45 * math.sin(angle), self.height * (0.3 + index * 0.13)]
            velocity = [self.generator.uniform(-0.45, 0.45), self.generator.uniform(-0.45, 0.45), self.generator.uniform(-0.4, 0.4)]
            self.balls.append({"position": position, "velocity": velocity, "color": _rgb(index / 4, 0.88, 1)})

    def _render_frame(self, delta):
        for ball in self.balls:
            for axis in range(3):
                ball["position"][axis] += ball["velocity"][axis] * delta
            distance = math.sqrt(sum(value * value for value in ball["position"]))
            limit = self.boundary - self.radius
            if distance > limit:
                normal = [value / distance for value in ball["position"]]
                ball["position"] = [normal[axis] * limit for axis in range(3)]
                speed_out = sum(ball["velocity"][axis] * normal[axis] for axis in range(3))
                if speed_out > 0:
                    ball["velocity"] = [ball["velocity"][axis] - 2 * speed_out * normal[axis] for axis in range(3)]

        for first_index, first in enumerate(self.balls):
            for second in self.balls[first_index + 1:]:
                delta_position = [second["position"][axis] - first["position"][axis] for axis in range(3)]
                distance = math.sqrt(sum(value * value for value in delta_position))
                if not 1e-9 < distance < 2 * self.radius:
                    continue
                normal = [value / distance for value in delta_position]
                relative_speed = sum((second["velocity"][axis] - first["velocity"][axis]) * normal[axis] for axis in range(3))
                if relative_speed < 0:
                    for axis in range(3):
                        first["velocity"][axis] += relative_speed * normal[axis]
                        second["velocity"][axis] -= relative_speed * normal[axis]
                overlap = 2 * self.radius - distance
                for axis in range(3):
                    first["position"][axis] -= normal[axis] * overlap * 0.5
                    second["position"][axis] += normal[axis] * overlap * 0.5

        frame = [(0, 0, 0)] * self.led_count
        for ball in self.balls:
            for index, point in enumerate(self.positions):
                glow = max(0.0, 1 - _distance(point, ball["position"]) / self.radius)
                if glow:
                    frame[index] = tuple(round(channel * glow) for channel in ball["color"])
        return frame