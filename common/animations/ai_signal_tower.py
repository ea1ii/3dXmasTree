import math

from common.animations.ai_base import SpatialAnimation, _rgb


class SignalTower(SpatialAnimation):
    name = "ai_signal_tower"
    author = "Carlos Gil & AI"
    description = "A moving beacon climbs the trunk and sends expanding rings outward."

    def _initialise_effect(self, _parameters):
        self.period = self.generator.uniform(4.0, 7.0)
        self.hue = self.generator.uniform(0.08, 0.16)
        self.width = max(self.tree_radius * 0.13, 0.025)

    def _render_frame(self, _delta):
        phase = (self.elapsed / self.period) % 1.0
        height = phase * self.height
        ring_radius = self.tree_radius * (0.08 + 0.92 * phase)
        color = _rgb(self.hue, 0.9, 1)
        frame = []
        for x, y, z in self.positions:
            radial = math.hypot(x, y)
            beacon = math.exp(-((z - height) / max(self.height * 0.06, 0.01)) ** 2) * math.exp(-(radial / self.width) ** 2)
            ring = math.exp(-((radial - ring_radius) / self.width) ** 2) * math.exp(-((z - height) / max(self.height * 0.1, 0.01)) ** 2)
            intensity = max(beacon, ring)
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame