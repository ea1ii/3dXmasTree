import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class DropCoalescence(SpatialAnimation):
    name = "ai_drop_coalescence"
    author = "Carlos Gil & AI"
    version = "0.1.3"
    description = "Distinct droplets merge, fall, rebound, and send ripples across the base."

    def _initialise_effect(self, _parameters):
        self.gravity = 3.2 * self.height
        self.drag = 0.08
        self.ground = 0.025 * self.height
        self.drop_limit = 32
        spacing = [
            _distance(first, second)
            for first, second in zip(self.positions, self.positions[1:])
            if _distance(first, second) > 0
        ]
        self.led_spacing = sum(spacing) / len(spacing) if spacing else self.height / 10
        self.maximum_drop_radius = max(self.led_spacing * 1.5, self.tree_radius * 0.22)
        self.merge_count = 0
        self.bounce_count = 0
        self.drops = [self._new_drop() for _ in range(self.drop_limit)]

    def _new_drop(self):
        radius = min(
            self.maximum_drop_radius * self.generator.uniform(0.32, 0.58),
            self.maximum_drop_radius,
        )
        angle = self.generator.uniform(0, 2 * math.pi)
        height = self.generator.uniform(self.height * 0.48, self.height * 0.92)
        cone_radius = self.tree_radius * (1 - height / self.height)
        radial = cone_radius * self.generator.uniform(0.0, 0.75)
        return {
            "mass": radius ** 3,
            "radius": radius,
            "position": [radial * math.cos(angle), radial * math.sin(angle), height],
            "velocity": [self.generator.uniform(-0.2, 0.2), self.generator.uniform(-0.2, 0.2), self.generator.uniform(-0.1, 0.1)],
            "splash": 0.0,
            "splash_radius": 0.0,
            "color": _rgb(self.generator.uniform(0.5, 0.62), 0.35, 1),
        }

    @staticmethod
    def _resolve_elastic_collision(first, second, normal, separation):
        inverse_first = 1.0 / first["mass"]
        inverse_second = 1.0 / second["mass"]
        relative_speed = sum(
            (second["velocity"][axis] - first["velocity"][axis]) * normal[axis]
            for axis in range(3)
        )
        if relative_speed < 0:
            impulse = -2 * relative_speed / (inverse_first + inverse_second)
            for axis in range(3):
                first["velocity"][axis] -= impulse * inverse_first * normal[axis]
                second["velocity"][axis] += impulse * inverse_second * normal[axis]

        overlap = first["radius"] + second["radius"] - separation
        for axis in range(3):
            first["position"][axis] -= normal[axis] * overlap * inverse_first / (inverse_first + inverse_second)
            second["position"][axis] += normal[axis] * overlap * inverse_second / (inverse_first + inverse_second)

    def _render_frame(self, delta):
        step_count = max(1, min(8, math.ceil(delta / 0.025)))
        step = delta / step_count
        for _ in range(step_count):
            for drop in self.drops:
                velocity = drop["velocity"]
                velocity[2] -= self.gravity * step
                for axis in range(3):
                    velocity[axis] *= max(0.0, 1.0 - self.drag * step)
                    drop["position"][axis] += velocity[axis] * step
                if drop["position"][2] < self.ground + drop["radius"] and velocity[2] < 0:
                    drop["position"][2] = self.ground + drop["radius"]
                    drop["velocity"][2] = abs(drop["velocity"][2]) * 0.74
                    drop["velocity"][0] += self.generator.uniform(-0.4, 0.4)
                    drop["velocity"][1] += self.generator.uniform(-0.4, 0.4)
                    drop["splash"] = 0.75
                    drop["splash_radius"] = drop["radius"]
                    self.bounce_count += 1
                drop["splash"] = max(0.0, drop["splash"] - step)
                if drop["splash"] > 0:
                    drop["splash_radius"] += self.tree_radius * 1.3 * step

            first_index = 0
            while first_index < len(self.drops):
                first = self.drops[first_index]
                second_index = first_index + 1
                while second_index < len(self.drops):
                    second = self.drops[second_index]
                    separation = _distance(first["position"], second["position"])
                    if separation >= first["radius"] + second["radius"]:
                        second_index += 1
                        continue
                    total_mass = first["mass"] + second["mass"]
                    merged_radius = total_mass ** (1 / 3)
                    delta_position = [second["position"][axis] - first["position"][axis] for axis in range(3)]
                    normal = [value / max(separation, 1e-9) for value in delta_position]
                    if merged_radius > self.maximum_drop_radius:
                        self._resolve_elastic_collision(first, second, normal, separation)
                        first["splash"] = max(first["splash"], 0.12)
                        second["splash"] = max(second["splash"], 0.12)
                        second_index += 1
                        continue

                    first_color = first["color"]
                    second_color = second["color"]
                    first["position"] = [
                        (first["position"][axis] * first["mass"] + second["position"][axis] * second["mass"]) / total_mass
                        for axis in range(3)
                    ]
                    first["velocity"] = [
                        (first["velocity"][axis] * first["mass"] + second["velocity"][axis] * second["mass"]) / total_mass
                        for axis in range(3)
                    ]
                    first["mass"] = total_mass
                    first["radius"] = merged_radius
                    first["color"] = tuple(
                        round((first_color[channel] * (total_mass - second["mass"]) + second_color[channel] * second["mass"]) / total_mass)
                        for channel in range(3)
                    )
                    first["splash"] = 0.28
                    self.drops.pop(second_index)
                    self.merge_count += 1
                first_index += 1
            while len(self.drops) < self.drop_limit:
                self.drops.append(self._new_drop())

        frame = [0.0] * self.led_count
        colors = [(0, 0, 0)] * self.led_count
        for drop in self.drops:
            for index, point in enumerate(self.positions):
                glow = max(0.0, 1 - _distance(point, drop["position"]) / max(drop["radius"] * 1.8, self.led_spacing * 0.65))
                if drop["splash"] > 0:
                    radial_distance = math.hypot(point[0] - drop["position"][0], point[1] - drop["position"][1])
                    ring_width = max(self.led_spacing * 0.7, drop["radius"])
                    ring = math.exp(-((radial_distance - drop["splash_radius"]) / ring_width) ** 2)
                    ring *= max(0.0, 1 - abs(point[2] - self.ground) / max(self.led_spacing * 1.5, 1e-4))
                    glow = max(glow, drop["splash"] * ring)
                if glow > frame[index]:
                    frame[index] = glow
                    colors[index] = drop["color"]
        return [tuple(round(channel * value) for channel in color) for color, value in zip(colors, frame)]