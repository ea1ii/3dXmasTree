import math
import random

from common.animations.ai_base import SpatialAnimation, _distance, _mix, _rgb, _smooth


class CandleRows(SpatialAnimation):
    name = "ai_candle_rows"
    author = "Carlos Gil & AI"
    description = "Warm LED rows flicker softly like a tree of candles."

    def _initialise_effect(self, _parameters):
        self.row_phases = [self.generator.random() for _ in range(9)]
        self.row_rates = [self.generator.uniform(0.25, 0.55) for _ in range(9)]

    def _render_frame(self, _delta):
        frame = []
        for _x, _y, z in self.positions:
            row = min(8, int(z / self.height * 9))
            flicker = 0.78 + 0.22 * max(
                0.0,
                math.sin(2 * math.pi * self.elapsed * self.row_rates[row] + self.row_phases[row]),
            )
            color = _rgb(0.105, 0.48, flicker)
            frame.append(tuple(round(channel * flicker) for channel in color))
        return frame
