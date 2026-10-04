import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class SunriseLayers(SpatialAnimation):
    name = "ai_sunrise_layers"
    author = "Carlos Gil & AI"
    description = "A red-gold-white sunrise rises from the base in broad layers."

    CYCLE_SECONDS = 24.0

    def _initialise_effect(self, _parameters):
        pass

    def _render_frame(self, _delta):
        progress = (self.elapsed % self.CYCLE_SECONDS) / self.CYCLE_SECONDS
        warm_front = min(1.0, progress * 1.35)
        frame = []
        for _x, _y, z in self.positions:
            if z > warm_front:
                frame.append((0, 0, 0))
                continue
            color_progress = min(1.0, z / max(warm_front, 1e-6))
            low = _mix((155, 12, 2), (255, 94, 8), _smooth(color_progress))
            color = _mix(low, (255, 238, 195), _smooth(max(0.0, color_progress - 0.55) / 0.45))
            frame.append(color)
        return frame
