import math

from common.animations.ai_base import SpatialAnimation, _mix, _rgb


class ThermalDiffusion(SpatialAnimation):
    name = "ai_thermal_diffusion"
    author = "Carlos Gil & AI"
    version = "0.1.1"
    description = "Hot spots spread through neighboring LEDs and cool by diffusion."

    def _initialise_effect(self, _parameters):
        self.neighbors = []
        for index, point in enumerate(self.positions):
            nearest = sorted(
                (candidate for candidate in range(self.led_count) if candidate != index),
                key=lambda candidate: sum((point[axis] - self.positions[candidate][axis]) ** 2 for axis in range(3)),
            )[:8]
            self.neighbors.append(nearest)
        self.temperature = [0.0] * self.led_count
        self.diffusivity = 1.6
        self.cooling = 0.035
        self.source_timer = 0.0
        self.sources = []
        self.substep = 1 / 60
        for _ in range(min(4, self.led_count)):
            self._add_heat_source()

    def _add_heat_source(self):
        self.sources.append((self.generator.randrange(self.led_count), self.generator.uniform(0.7, 1.0), self.generator.uniform(2.0, 4.0)))

    def _render_frame(self, delta):
        self.source_timer -= delta
        if self.source_timer <= 0:
            for _ in range(self.generator.randint(2, 4)):
                self._add_heat_source()
            self.source_timer = self.generator.uniform(0.18, 0.55)
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            updated = self.temperature.copy()
            for index, value in enumerate(self.temperature):
                neighbor_average = sum(self.temperature[n] for n in self.neighbors[index]) / max(1, len(self.neighbors[index]))
                heat_source = sum(amplitude for source, amplitude, lifetime in self.sources if source == index)
                updated[index] = max(0.0, min(1.0, value + (self.diffusivity * (neighbor_average - value) + heat_source - self.cooling * value) * step))
            self.temperature = updated
            self.sources = [(source, amplitude, lifetime - step) for source, amplitude, lifetime in self.sources if lifetime > step]
            remaining -= step
        frame = []
        for temperature in self.temperature:
            color = _mix((15, 42, 190), (255, 74, 8), temperature)
            intensity = 0.1 + 0.9 * temperature
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame