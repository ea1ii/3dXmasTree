import math

from common.animations.ai_base import SpatialAnimation, _rgb


class ConvectionCells(SpatialAnimation):
    name = "ai_convection_cells"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "A buoyant heat field circulates in rising and sinking convection cells."

    def _initialise_effect(self, _parameters):
        self.levels = 20
        self.sectors = 18
        self.temperature = [[0.0 for _ in range(self.sectors)] for _ in range(self.levels)]
        self.velocity = [[0.0 for _ in range(self.sectors)] for _ in range(self.levels)]
        self.substep = 1 / 45
        self.diffusion = 0.28
        self.buoyancy = 4.2
        self.drag = 0.62

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            next_temperature = [row.copy() for row in self.temperature]
            next_velocity = [row.copy() for row in self.velocity]
            for level in range(self.levels):
                for sector in range(self.sectors):
                    left = self.temperature[level][(sector - 1) % self.sectors]
                    right = self.temperature[level][(sector + 1) % self.sectors]
                    below = self.temperature[max(0, level - 1)][sector]
                    above = self.temperature[min(self.levels - 1, level + 1)][sector]
                    temperature = self.temperature[level][sector]
                    source = (
                        1.8 * max(0.0, math.sin(self.elapsed * 1.8 + sector * 1.7))
                        if level < 2
                        else 0.0
                    )
                    conduction = self.diffusion * (left + right + below + above - 4 * temperature)
                    next_temperature[level][sector] = min(1.0, max(0.0, temperature + (conduction + source - 0.12 * temperature) * step))
                    next_velocity[level][sector] = max(-1.2, min(1.2, self.velocity[level][sector] + (self.buoyancy * (temperature - 0.25) - self.drag * self.velocity[level][sector]) * step))
            self.temperature = next_temperature
            self.velocity = next_velocity
            remaining -= step

        frame = []
        for x, y, z in self.positions:
            level = min(self.levels - 1, max(0, int(z / self.height * self.levels)))
            sector = int((math.atan2(y, x) % (2 * math.pi)) / (2 * math.pi) * self.sectors)
            heat = self.temperature[level][sector]
            vertical_speed = self.velocity[level][sector]
            hue = 0.58 - 0.52 * heat if vertical_speed >= 0 else 0.58 + 0.08 * (1 - heat)
            intensity = min(1.0, 0.42 + heat * 0.58)
            frame.append(tuple(round(channel * intensity) for channel in _rgb(hue, 0.9, 1)))
        return frame