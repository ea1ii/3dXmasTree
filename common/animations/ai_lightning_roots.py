import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class LightningRoots(SpatialAnimation):
    name = "ai_lightning_roots"
    author = "Carlos Gil & AI"
    description = "Branching blue-white lightning bolts crackle up from the roots."

    def _initialise_effect(self, _parameters):
        self.remaining = 0.0
        self.next_bolt = 0.0
        self.flash_duration = 0.14
        self.paths = []

    def _new_bolt(self):
        bands = [[] for _ in range(12)]
        for index, (_x, _y, z) in enumerate(self.positions):
            bands[min(11, int(z / self.height * 12))].append(index)
        self.paths = []
        for _branch in range(self.generator.randint(2, 4)):
            path = []
            for band in bands:
                if band and self.generator.random() < 0.82:
                    path.append(self.generator.choice(band))
            self.paths.append(path)
        self.remaining = self.flash_duration
        self.next_bolt = self.generator.uniform(1.2, 4.5)

    def _render_frame(self, delta):
        self.remaining = max(0.0, self.remaining - delta)
        if self.remaining == 0:
            self.next_bolt -= delta
            if self.next_bolt <= 0:
                self._new_bolt()
        frame = [(0, 0, 0)] * self.led_count
        if self.remaining > 0:
            decay = self.remaining / self.flash_duration
            for path in self.paths:
                for index in path:
                    frame[index] = (round(150 * decay), round(215 * decay), 255)
        return frame
