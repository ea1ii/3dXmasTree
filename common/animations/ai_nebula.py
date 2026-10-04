import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class Nebula(SpatialAnimation):
    name = "ai_nebula"
    author = "Carlos Gil & AI"
    description = "Layered violet, teal, and blue cloud fields drift through 3D space."

    def _initialise_effect(self, _parameters):
        self.waves = [
            (
                tuple(self.generator.uniform(-5, 5) for _ in range(3)),
                self.generator.uniform(0.3, 1.0),
                self.generator.uniform(0, 2 * math.pi),
            )
            for _ in range(5)
        ]

    def _render_frame(self, _delta):
        frame = []
        for point in self.positions:
            noise = sum(
                math.sin(sum(a * b for a, b in zip(point, vector)) + self.elapsed * speed + phase)
                for vector, speed, phase in self.waves
            ) / len(self.waves)
            hue = 0.56 + 0.22 * (0.5 + 0.5 * noise)
            value = 0.12 + 0.88 * max(0.0, 0.5 + 0.5 * noise) ** 1.6
            frame.append(_rgb(hue, 0.78, value))
        return frame
