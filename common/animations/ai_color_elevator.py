import math

from common.animations.ai_base import SpatialAnimation, _rgb


class ColorElevator(SpatialAnimation):
    name = "ai_color_elevator"
    author = "Carlos Gil & AI"
    description = "Colored horizontal bands rise through the tree at different rates."

    def _initialise_effect(self, _parameters):
        self.bands = [
            (self.generator.random(), self.generator.uniform(0.12, 0.32), _rgb(self.generator.random(), 0.9, 1))
            for _ in range(5)
        ]

    def _render_frame(self, _delta):
        frame = []
        for _x, _y, z in self.positions:
            intensity = 0.0
            color = (0, 0, 0)
            for phase, speed, band_color in self.bands:
                center = (phase + self.elapsed * speed) % 1.2 - 0.1
                glow = max(0.0, 1 - abs(z - center) / 0.12)
                if glow > intensity:
                    intensity, color = glow, band_color
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame