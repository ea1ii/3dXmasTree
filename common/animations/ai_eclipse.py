import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class Eclipse(SpatialAnimation):
    name = "ai_eclipse"
    author = "Carlos Gil & AI"
    description = "A dark 3D eclipse travels across a dim blue-violet star field."

    def _initialise_effect(self, _parameters):
        self.radius = max(self.tree_radius * 0.58, 0.1)
        self.halo_width = max(self.tree_radius * 0.24, 0.04)
        self.phase = self.generator.random() * 2 * math.pi
        self.speed = self.generator.uniform(0.12, 0.22)

    def _render_frame(self, _delta):
        center = (
            self.tree_radius * 0.55 * math.sin(self.elapsed * self.speed + self.phase),
            self.tree_radius * 0.55 * math.cos(self.elapsed * self.speed * 0.7 + self.phase),
            self.height * (0.25 + 0.5 * (0.5 + 0.5 * math.sin(self.elapsed * self.speed))),
        )
        frame = []
        for x, y, z in self.positions:
            distance = _distance((x, y, z), center)
            background_pulse = 0.72 + 0.28 * (
                0.5 + 0.5 * math.sin(math.atan2(y, x) * 3 + z * 6 - self.elapsed * 0.8)
            )
            field = tuple(
                round(channel * background_pulse)
                for channel in (18, 24, 110)
            )
            rim = math.exp(-((distance - self.radius) / self.halo_width) ** 2)
            if distance < self.radius:
                shadow_factor = 0.08 + 0.08 * min(1.0, distance / self.radius)
                color = tuple(round(channel * shadow_factor) for channel in field)
            else:
                rim_color = (95, 170, 255)
                color = tuple(
                    min(255, base + round(glow * rim))
                    for base, glow in zip(field, rim_color)
                )
            frame.append(color)
        return frame
