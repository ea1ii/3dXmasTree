import math

from common.animations.ai_base import SpatialAnimation, _mix


class DayFinale(SpatialAnimation):
    name = "ai_day_finale"
    author = "Carlos Gil & AI"
    description = "A red, cold-white, and green gradient rotates around the tree as it fades to black."

    PALETTE = (
        (255, 18, 28),
        (218, 240, 255),
        (38, 145, 72),
    )

    # Overrides SpatialAnimation._initialise_effect.
    def _initialise_effect(self, _parameters):
        self.gradient_phase = self.generator.random()
        self.rotation_speed = self.generator.choice((-1.0, 1.0)) * self.generator.uniform(0.025, 0.08)
        self.fade_duration = self.generator.uniform(45.0, 75.0)

    def _gradient_color(self, position):
        scaled_position = (position % 1.0) * len(self.PALETTE)
        start_index = int(scaled_position)
        blend = scaled_position - start_index
        end_index = (start_index + 1) % len(self.PALETTE)
        return _mix(self.PALETTE[start_index], self.PALETTE[end_index], blend)

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, _delta):
        brightness = max(0.0, 1.0 - self.elapsed / self.fade_duration)
        if brightness <= 0.0:
            return [(0, 0, 0)] * self.led_count

        rotation = self.gradient_phase + self.elapsed * self.rotation_speed / (2 * math.pi)
        frame = []
        for x, y, _z in self.positions:
            angular_position = math.atan2(y, x) / (2 * math.pi) + rotation
            color = self._gradient_color(angular_position)
            frame.append(tuple(round(channel * brightness) for channel in color))
        return frame
