import math

from common.animations.ai_base import SpatialAnimation, _rgb, _smooth


class LastLight(SpatialAnimation):
    name = "ai_last_light"
    author = "Carlos Gil & AI"
    description = "The tree darkens to one central LED, then sends light back outward."
    COLLAPSE_DURATION_RANGE = (5.0, 8.0)
    RETURN_DURATION_RANGE = (3.0, 5.0)

    def _initialise_effect(self, _parameters):
        self.center = (0.0, 0.0, self.height * 0.5)
        self.radii = [math.sqrt(x * x + y * y + (z - self.center[2]) ** 2) for x, y, z in self.positions]
        self.max_radius = max(self.radii, default=1.0)
        self.point_index = min(range(self.led_count), key=lambda index: self.radii[index])
        self.point_radius = self.radii[self.point_index]
        self.phase = "collapse"
        self.phase_elapsed = 0.0
        self.phase_duration = self.generator.uniform(*self.COLLAPSE_DURATION_RANGE)
        self.color = _rgb(self.generator.random(), 0.85, 1)

    def _render_frame(self, delta):
        self.phase_elapsed += delta
        if self.phase_elapsed >= self.phase_duration:
            if self.phase == "collapse":
                self.phase = "return"
                self.phase_duration = self.generator.uniform(*self.RETURN_DURATION_RANGE)
            else:
                self.phase = "collapse"
                self.phase_duration = self.generator.uniform(*self.COLLAPSE_DURATION_RANGE)
                self.color = _rgb(self.generator.random(), 0.85, 1)
            self.phase_elapsed = 0.0
        progress = _smooth(self.phase_elapsed / self.phase_duration)
        radius = self.max_radius * (1 - progress if self.phase == "collapse" else progress)
        frame = [self.color if distance <= radius else (0, 0, 0) for distance in self.radii]
        if radius <= max(self.point_radius, self.max_radius * 0.01):
            frame = [(0, 0, 0)] * self.led_count
            frame[self.point_index] = self.color
        return frame