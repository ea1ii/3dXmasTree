import math

from common.animations.ai_base import SpatialAnimation, _rgb, _smooth


class Resonance(SpatialAnimation):
    name = "ai_resonance"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "A driven damped oscillator brightens as its drive crosses resonance."

    def _initialise_effect(self, _parameters):
        self.natural_frequency = self.generator.uniform(5.0, 9.0)
        self.damping_ratio = self.generator.uniform(0.08, 0.2)
        self.drive_start = self.natural_frequency * 0.35
        self.drive_end = self.natural_frequency * 1.8
        self.position = 0.0
        self.velocity = 0.0
        self.amplitude = 0.0
        self.substep = 1 / 120
        self.color_low = _rgb(0.58, 0.85, 1)
        self.color_high = _rgb(0.1, 0.95, 1)

    def _render_frame(self, delta):
        drive_fraction = 0.5 + 0.5 * math.sin(self.elapsed * 0.55)
        drive_frequency = self.drive_start + (self.drive_end - self.drive_start) * drive_fraction
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            acceleration = (
                math.sin(self.elapsed * drive_frequency) * 6.0
                - 2 * self.damping_ratio * self.natural_frequency * self.velocity
                - self.natural_frequency ** 2 * self.position
            )
            self.velocity += acceleration * step
            self.position += self.velocity * step
            self.amplitude = min(1.0, abs(self.position) * 0.45)
            remaining -= step
        resonance_distance = abs(drive_frequency - self.natural_frequency) / self.natural_frequency
        glow = max(self.amplitude, 1 - _smooth(resonance_distance))
        color = tuple(round(a + (b - a) * glow) for a, b in zip(self.color_low, self.color_high))
        return [
            tuple(round(channel * glow * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * z * 3 + self.elapsed * 0.4)))) for channel in color)
            for _x, _y, z in self.positions
        ]