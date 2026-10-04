import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class Constellation(SpatialAnimation):
    name = "ai_constellation"
    author = "Carlos Gil & AI"
    description = "Sparse blue-white stars twinkle independently across the tree."

    def _initialise_effect(self, _parameters):
        self.phases = [self.generator.random() for _ in self.positions]
        self.rates = [self.generator.uniform(0.05, 0.22) for _ in self.positions]
        self.thresholds = [self.generator.uniform(0.72, 0.94) for _ in self.positions]

    def _render_frame(self, _delta):
        frame = []
        for phase, rate, threshold in zip(self.phases, self.rates, self.thresholds):
            twinkle = max(0.0, math.sin(2 * math.pi * (self.elapsed * rate + phase)))
            intensity = _smooth((twinkle - threshold) / (1 - threshold))
            frame.append(tuple(round(channel * intensity) for channel in (155, 205, 255)))
        return frame
