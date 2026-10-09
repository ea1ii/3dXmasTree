import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class GranularAvalanche(SpatialAnimation):
    name = "ai_granular_avalanche"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "Grains accelerate down branches and collide in small avalanches."

    def _initialise_effect(self, _parameters):
        self.gravity = 3.0 * self.height
        self.grain_count = 80
        self.grains = [self._new_grain() for _ in range(self.grain_count)]
        self.settled_elapsed = 0.0
        self.color = _rgb(0.09, 0.8, 1)

    def _new_grain(self):
        angle = self.generator.uniform(0, 2 * math.pi)
        height = self.generator.uniform(0.35, 1.0) * self.height
        radius = self.tree_radius * (1 - height / self.height) * 0.88
        return {
            "angle": angle,
            "height": height,
            "speed": self.generator.uniform(0.25, 0.6) * self.height,
            "stick_angle": self.generator.uniform(0.18, 0.48),
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

        if all(grain["height"] <= 0.0 for grain in self.grains):
            self.settled_elapsed += delta
            if self.settled_elapsed >= 1.0:
                self.grains = [self._new_grain() for _ in range(self.grain_count)]
                self.settled_elapsed = 0.0
        else:
            self.settled_elapsed = 0.0

        for first_index, first in enumerate(self.grains):
            for second in self.grains[first_index + 1:]:
                angular_distance = abs((first["angle"] - second["angle"] + math.pi) % (2 * math.pi) - math.pi)
                if angular_distance < 0.22 and abs(first["height"] - second["height"]) < self.height * 0.055:
                    first["speed"], second["speed"] = (
                        second["speed"] * 0.9 + self.height * 0.08,
                        first["speed"] * 0.9 + self.height * 0.08,
                    )
        frame_strength = [0.0] * self.led_count
        for grain in self.grains:
            radius = self.tree_radius * (1 - grain["height"] / self.height) * 0.92
            center = (radius * math.cos(grain["angle"]), radius * math.sin(grain["angle"]), grain["height"])
            nearest = min(range(self.led_count), key=lambda index: _distance(self.positions[index], center))
            speed_factor = min(1.0, grain["speed"] / max(self.height * 0.5, 1e-6))
            for offset in range(-3, 4):
                index = nearest + offset
                if 0 <= index < self.led_count:
                    strength = max(0.0, 1.0 - abs(offset) / 4) * (0.6 + 0.4 * speed_factor)
                    frame_strength[index] = max(frame_strength[index], strength)
        return [tuple(round(channel * strength) for channel in self.color) for strength in frame_strength]
