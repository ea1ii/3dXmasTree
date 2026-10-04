import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class ColorMosaic(SpatialAnimation):
    name = "ai_color_mosaic"
    author = "Carlos Gil & AI"
    description = "Irregular 3D color patches slowly trade hues."

    def _initialise_effect(self, _parameters):
        self.seeds = [self.generator.choice(self.positions) for _ in range(12)]
        self.hues = [self.generator.random() for _ in self.seeds]
        self.patch_for_led = [
            min(range(len(self.seeds)), key=lambda index: _distance(point, self.seeds[index]))
            for point in self.positions
        ]
        self.patch_phases = [self.generator.uniform(0, 2 * math.pi) for _ in self.seeds]

    def _render_frame(self, _delta):
        colors = [
            _rgb(hue + 0.035 * math.sin(self.elapsed * 0.12 + phase), 0.82, 1)
            for hue, phase in zip(self.hues, self.patch_phases)
        ]
        return [colors[index] for index in self.patch_for_led]