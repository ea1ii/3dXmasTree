import math

from common.animations.ai_base import SpatialAnimation, _rgb


class DiamondLattice(SpatialAnimation):
    name = "ai_diamond_lattice"
    author = "Carlos Gil & AI"
    description = "Rotating diagonal light lines form a colorful 3D diamond lattice."

    def _initialise_effect(self, _parameters):
        self.rotation = self.generator.random() * 2 * math.pi
        self.speed = self.generator.uniform(0.04, 0.12)
        self.density = self.generator.uniform(3.0, 5.5)

    def _render_frame(self, _delta):
        rotation = self.rotation + self.elapsed * self.speed
        frame = []
        for x, y, z in self.positions:
            angle = math.atan2(y, x) - rotation
            wave = math.sin(self.density * (angle + z * 3.5))
            distance = abs(wave)
            intensity = max(0.0, 1.0 - distance / 0.22) ** 2
            frame.append(tuple(round(channel * intensity) for channel in _rgb(0.54 + 0.18 * math.sin(angle), 0.9, 1)))
        return frame