import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class DropCoalescence(SpatialAnimation):
    name = "ai_drop_coalescence"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "Gravity-driven droplets merge, fall, and rebound in luminous splashes."

    def _initialise_effect(self, _parameters):
        self.gravity = 3.2 * self.height
        self.drag = 0.08
        self.ground = 0.025 * self.height
        self.drop_limit = 32
        self.drops = [self._new_drop() for _ in range(self.drop_limit)]

    def _new_drop(self):
        radius = self.generator.uniform(0.08, 0.16) * max(self.tree_radius, 0.2)
        angle = self.generator.uniform(0, 2 * math.pi)
        height = self.generator.uniform(self.height * 0.35, self.height)
        radial = self.tree_radius * self.generator.uniform(0.0, 0.6)
        return {
            "mass": radius ** 3,
            "radius": radius,
            "position": [radial * math.cos(angle), radial * math.sin(angle), height],
            "velocity": [self.generator.uniform(-0.15, 0.15), self.generator.uniform(-0.15, 0.15), 0.0],
            "splash": 0.0,
        }

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
                if drop["position"][2] < self.ground + drop["radius"]:
                    drop["position"][2] = self.ground + drop["radius"]
                    drop["velocity"][2] = abs(drop["velocity"][2]) * 0.58
                    drop["splash"] = 0.75
                drop["splash"] = max(0.0, drop["splash"] - step)

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
                    first["position"] = [
                        (first["position"][axis] * first["mass"] + second["position"][axis] * second["mass"]) / total_mass
                        for axis in range(3)
                    ]
                    first["velocity"] = [
                        (first["velocity"][axis] * first["mass"] + second["velocity"][axis] * second["mass"]) / total_mass
                        for axis in range(3)
                    ]
                    first["mass"] = total_mass
                    first["radius"] = total_mass ** (1 / 3)
                    self.drops.pop(second_index)
                first_index += 1
            while len(self.drops) < self.drop_limit:
                self.drops.append(self._new_drop())

        frame = [0.0] * self.led_count
        for drop in self.drops:
            for index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, drop["position"]) / max(drop["radius"] * 4.5, 1e-4)) ** 2)
                if drop["splash"] > 0:
                    glow = max(glow, drop["splash"] * math.exp(-((point[2] - self.ground) / max(drop["radius"] * 2, 1e-4)) ** 2))
                frame[index] = max(frame[index], glow)
        color = (195, 230, 255)
        return [tuple(round(channel * value) for channel in color) for value in frame]