import math

from common.animations.ai_base import SpatialAnimation, _rgb


class SpringChain(SpatialAnimation):
    name = "ai_spring_chain"
    author = "Carlos Gil & AI"
    description = "A plucked damped spring chain sends elastic waves along the LEDs."

    def _initialise_effect(self, _parameters):
        self.displacement = [0.0] * self.led_count
        self.velocity = [0.0] * self.led_count
        self.displacement[self.led_count // 2] = self.height * 0.18
        self.spring = 22.0
        self.damping = 1.35
        self.drive = self.generator.uniform(0.0, 0.04) * self.height
        self.substep = 1 / 120
        self.color = _rgb(self.generator.uniform(0.45, 0.58), 0.9, 1)

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            next_displacement = self.displacement.copy()
            for index in range(self.led_count):
                left = self.displacement[index - 1] if index else 0.0
                right = self.displacement[index + 1] if index + 1 < self.led_count else 0.0
                acceleration = self.spring * (left + right - 2 * self.displacement[index])
                acceleration -= self.damping * self.velocity[index]
                if index == self.led_count // 2:
                    acceleration += self.drive * math.sin(self.elapsed * 1.7)
                self.velocity[index] += acceleration * step
                next_displacement[index] += self.velocity[index] * step
            self.displacement = next_displacement
            remaining -= step
        return [
            tuple(round(channel * min(1.0, abs(value) / max(self.height * 0.16, 1e-6))) for channel in self.color)
            for value in self.displacement
        ]