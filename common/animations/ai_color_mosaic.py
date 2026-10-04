import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class ColorMosaic(SpatialAnimation):
    name = "ai_color_mosaic"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Irregular 3D color patches slowly trade hues."

    def _initialise_effect(self, _parameters):
        self.seeds = [self.generator.choice(self.positions) for _ in range(12)]
        self.hues = [self.generator.random() for _ in self.seeds]
        self.patch_phases = [self.generator.uniform(0, 2 * math.pi) for _ in self.seeds]
        self.patch_speeds = [self.generator.uniform(0.1, 0.28) for _ in self.seeds]
        self.hue_speeds = [self.generator.uniform(-0.035, 0.035) for _ in self.seeds]

    def _render_frame(self, _delta):
        moving_seeds = [
            (
                x + self.tree_radius * 0.14 * math.sin(self.elapsed * speed + phase),
                y + self.tree_radius * 0.14 * math.cos(self.elapsed * speed * 0.8 + phase),
                z + self.height * 0.08 * math.sin(self.elapsed * speed * 0.6 + phase),
            )
            for (x, y, z), speed, phase in zip(self.seeds, self.patch_speeds, self.patch_phases)
        ]
        colors = [
            _rgb(hue + speed * self.elapsed, 0.9, 1)
            for hue, speed in zip(self.hues, self.hue_speeds)
        ]
        return [
            colors[min(range(len(moving_seeds)), key=lambda index: _distance(point, moving_seeds[index]))]
            for point in self.positions
        ]