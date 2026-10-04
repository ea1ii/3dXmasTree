import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class CometTrain(SpatialAnimation):
    name = "ai_comet_train"
    author = "Carlos Gil & AI"
    description = "Colored comets orbit the tree with independent 3D tails."

    def _initialise_effect(self, _parameters):
        self.comets = [
            (
                self.generator.uniform(0, 2 * math.pi),
                self.generator.uniform(0.2, 0.7),
                self.generator.choice((-1, 1)) * self.generator.uniform(0.08, 0.18),
                self.generator.uniform(0.15, 0.35),
                _rgb(self.generator.random(), 0.85, 1),
            )
            for _ in range(4)
        ]

    def _render_frame(self, _delta):
        strengths = [0.0] * self.led_count
        colors = [(0, 0, 0)] * self.led_count
        for phase, start_height, speed, tail_length, color in self.comets:
            height = (start_height + self.elapsed * speed) % 1.0
            angle = phase + self.elapsed * 2.2
            radius = self.tree_radius * (0.72 * (1 - height) + 0.08)
            head = (radius * math.cos(angle), radius * math.sin(angle), height * self.height)
            for index, point in enumerate(self.positions):
                distance = _distance(point, head)
                intensity = max(0.0, 1.0 - distance / tail_length)
                intensity = intensity ** 2
                if intensity > strengths[index]:
                    strengths[index] = intensity
                    colors[index] = color
        return [tuple(round(channel * value) for channel in color) for color, value in zip(colors, strengths)]
