import math

from common.animations.ai_base import SpatialAnimation, _rgb


class CatherineWheel(SpatialAnimation):
    name = "ai_catherine_wheel"
    author = "Carlos Gil & AI"
    description = "Rotating colored spokes flare out from the tree's center."

    def _initialise_effect(self, _parameters):
        self.spokes = self.generator.randint(5, 9)
        self.phase = self.generator.random() * 2 * math.pi
        self.rate = self.generator.uniform(0.2, 0.55)
        self.colors = [_rgb(self.generator.random(), 0.92, 1) for _ in range(self.spokes)]

    def _render_frame(self, _delta):
        rotation = self.elapsed * self.rate + self.phase
        frame = []
        for x, y, z in self.positions:
            angle = (math.atan2(y, x) - rotation) % (2 * math.pi)
            spoke = round(angle / (2 * math.pi) * self.spokes) % self.spokes
            target = spoke * (2 * math.pi / self.spokes)
            difference = abs((angle - target + math.pi) % (2 * math.pi) - math.pi)
            radial = math.hypot(x, y)
            active = 0.12 <= radial <= self.tree_radius * 1.15 and difference < 0.12
            frame.append(self.colors[spoke] if active else (0, 0, 0))
        return frame