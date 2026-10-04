import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class FireflySwarm(SpatialAnimation):
    name = "ai_firefly_swarm"
    author = "Carlos Gil & AI"
    description = "Warm fireflies wander, gather, and scatter around the branches."
    FLY_COUNT = 24
    GLOW_RADIUS_TREE_RATIO = 0.17

    def _initialise_effect(self, _parameters):
        self.flies = [
            (
                self.generator.uniform(0, 2 * math.pi),
                self.generator.uniform(0, 2 * math.pi),
                self.generator.uniform(0.3, 1.0),
                self.generator.uniform(0.2, 0.8),
                self.generator.random(),
            )
            for _ in range(self.FLY_COUNT)
        ]

    def _render_frame(self, _delta):
        strengths = [0.0] * self.led_count
        for phase, vertical_phase, speed, radius_scale, pulse_phase in self.flies:
            angle = phase + self.elapsed * speed
            z = 0.08 + 0.84 * (0.5 + 0.5 * math.sin(vertical_phase + self.elapsed * speed * 0.55))
            radius = self.tree_radius * radius_scale * (1 - z * 0.7)
            center = (radius * math.cos(angle), radius * math.sin(angle), z * self.height)
            pulse = 0.22 + 0.78 * max(
                0.0,
                math.sin(2 * math.pi * self.elapsed * 0.35 + pulse_phase),
            ) ** 1.5
            glow_radius = max(self.tree_radius * self.GLOW_RADIUS_TREE_RATIO, 0.025)
            for index, point in enumerate(self.positions):
                glow = math.exp(-(_distance(point, center) / glow_radius) ** 2) * pulse
                strengths[index] = max(strengths[index], glow)
        return [tuple(round(channel * intensity) for channel in (255, 170, 65)) for intensity in strengths]
