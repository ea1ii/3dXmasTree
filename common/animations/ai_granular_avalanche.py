import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class GranularAvalanche(SpatialAnimation):
    name = "ai_granular_avalanche"
    author = "Carlos Gil & AI"
    description = "Grains accelerate down branches and collide in small avalanches."

    def _initialise_effect(self, _parameters):
        self.gravity = 1.1 * self.height
        self.grains = [self._new_grain() for _ in range(18)]
        self.color = _rgb(0.09, 0.8, 1)

    def _new_grain(self):
        angle = self.generator.uniform(0, 2 * math.pi)
        height = self.generator.uniform(0.35, 1.0) * self.height
        radius = self.tree_radius * (1 - height / self.height) * 0.88
        return {
            "angle": angle,
            "height": height,
            "speed": self.generator.uniform(0.0, 0.15) * self.height,
            "stick_angle": self.generator.uniform(0.25, 0.55),
        }

    def _render_frame(self, delta):
        for grain in self.grains:
            height = grain["height"]
            local_radius = self.tree_radius * (1 - height / self.height)
            slope = math.atan2(self.height, max(self.tree_radius, 1e-4))
            if slope > grain["stick_angle"]:
                grain["speed"] += self.gravity * math.sin(slope) * delta
            else:
                grain["speed"] *= math.exp(-1.8 * delta)
            grain["height"] -= grain["speed"] * delta
            grain["angle"] += math.sin(self.elapsed + grain["height"] * 4) * 0.12 * delta
            grain["height"] = min(self.height, max(0.0, grain["height"]))

        for first_index, first in enumerate(self.grains):
            for second in self.grains[first_index + 1:]:
                angular_distance = abs((first["angle"] - second["angle"] + math.pi) % (2 * math.pi) - math.pi)
                if angular_distance < 0.22 and abs(first["height"] - second["height"]) < self.height * 0.055:
                    first["speed"], second["speed"] = second["speed"] * 0.75, first["speed"] * 0.75
        frame = [(0, 0, 0)] * self.led_count
        for grain in self.grains:
            radius = self.tree_radius * (1 - grain["height"] / self.height) * 0.9
            center = (radius * math.cos(grain["angle"]), radius * math.sin(grain["angle"]), grain["height"])
            for index, point in enumerate(self.positions):
                if _distance(point, center) < max(self.tree_radius * 0.09, 0.02):
                    frame[index] = self.color
        return frame
