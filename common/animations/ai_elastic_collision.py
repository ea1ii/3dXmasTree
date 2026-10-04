import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class ElasticCollision(SpatialAnimation):
    name = "ai_elastic_collision"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "Luminous spheres exchange momentum in elastic 3D collisions."

    def _initialise_effect(self, _parameters):
        self.radius = max(self.tree_radius * 0.32, self.height * 0.1, 0.05)
        self.boundary = max(self.tree_radius * 0.92, self.height * 0.42, 0.12)
        self.center_z = self.height * 0.5
        self.balls = []
        self.ball_count = 8
        for index in range(self.ball_count):
            angle = 2 * math.pi * index / self.ball_count + self.generator.uniform(-0.12, 0.12)
            radial = self.boundary * self.generator.uniform(0.28, 0.62)
            position = [radial * math.cos(angle), radial * math.sin(angle), self.center_z + self.height * self.generator.uniform(-0.24, 0.24)]
            velocity = [self.generator.uniform(-1.4, 1.4), self.generator.uniform(-1.4, 1.4), self.generator.uniform(-1.2, 1.2)]
            self.balls.append({"position": position, "velocity": velocity, "color": _rgb(index / self.ball_count, 0.88, 1)})

    def _render_frame(self, delta):
        for ball in self.balls:
            for axis in range(3):
                ball["position"][axis] += ball["velocity"][axis] * delta
            relative_position = [ball["position"][0], ball["position"][1], ball["position"][2] - self.center_z]
            distance = math.sqrt(sum(value * value for value in relative_position))
            limit = self.boundary - self.radius
            if distance > limit:
                normal = [value / distance for value in relative_position]
                ball["position"] = [normal[0] * limit, normal[1] * limit, self.center_z + normal[2] * limit]
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