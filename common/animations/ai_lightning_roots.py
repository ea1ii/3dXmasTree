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
        self.beam_width = max(self.tree_radius * 0.2, self.height * 0.025)

    def _new_bolt(self):
        bands = [[] for _ in range(16)]
        for index, (_x, _y, z) in enumerate(self.positions):
            bands[min(15, int(z / self.height * 16))].append(index)
        self.paths = []
        for _branch in range(self.generator.randint(4, 7)):
            path = []
            for band in bands:
                if band and self.generator.random() < 0.92:
                    path.append(self.generator.choice(band))
            self.paths.append(path)
        self.beam_width = max(
            self.tree_radius * self.generator.uniform(0.18, 0.28),
            self.height * 0.025,
        )
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
            width = self.beam_width
            for path in self.paths:
                for led_index, point in enumerate(self.positions):
                    distance = min(
                        (_distance(point, self.positions[index]) for index in path),
                        default=math.inf,
                    )
                    glow = max(0.0, 1.0 - distance / width) * decay
                    if glow > 0.0:
                        frame[led_index] = (
                            round(150 * glow),
                            round(215 * glow),
                            round(255 * glow),
                        )
        return frame
