import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class EmberBreath(SpatialAnimation):
    name = "ai_ember_breath"
    author = "Carlos Gil & AI"
    description = "Uneven red-orange embers breathe at different speeds."

    def _initialise_effect(self, _parameters):
        self.phases = [self.generator.random() for _ in self.positions]
        self.rates = [self.generator.uniform(0.06, 0.2) for _ in self.positions]
        self.hues = [self.generator.uniform(0.005, 0.095) for _ in self.positions]

    def _render_frame(self, _delta):
        frame = []
        for phase, rate, hue in zip(self.phases, self.rates, self.hues):
            pulse = max(0.0, math.sin(2 * math.pi * (self.elapsed * rate + phase)))
            intensity = 0.08 + 0.92 * pulse ** 3
            frame.append(tuple(round(channel * intensity) for channel in _rgb(hue, 1, 1)))
        return frame
