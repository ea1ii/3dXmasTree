import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Volcano(SpatialAnimation):
    name = "ai_volcano"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Warm eruptions launch colored sparks from the tree base."

    def _initialise_effect(self, _parameters):
        self.particle_count = 48
        self.particles = [self._new_particle() for _ in range(self.particle_count)]

    def _new_particle(self):
        angle = self.generator.uniform(0, 2 * math.pi)
        speed = self.generator.uniform(0.45, 1.0) * self.height
        return {
            "age": self.generator.uniform(0, 1.5),
            "life": self.generator.uniform(0.9, 2.2),
            "vx": speed * math.cos(angle),
            "vy": speed * math.sin(angle),
            "vz": self.generator.uniform(1.0, 1.8) * self.height,
            "color": _rgb(self.generator.uniform(0.01, 0.13), 1, 1),
        }

    def _render_frame(self, delta):
        frame = [0.0] * self.led_count
        width = max(self.tree_radius * 0.2, 0.045)
        for index, particle in enumerate(self.particles):
            particle["age"] += delta
            if particle["age"] >= particle["life"]:
                self.particles[index] = particle = self._new_particle()
            age = particle["age"]
            center = (
                particle["vx"] * age * 0.38,
                particle["vy"] * age * 0.38,
                particle["vz"] * age - 0.5 * self.height * age * age,
            )
            fade = max(0.0, 1 - age / particle["life"])
            for led_index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, center) / width) ** 2) * fade
                frame[led_index] = max(frame[led_index], glow)
        return [
            tuple(round(channel * strength) for channel in (255, 88, 12))
            if strength <= 0
            else tuple(round(channel * strength) for channel in _rgb(0.04 + 0.05 * strength, 1, 1))
            for strength in frame
        ]