import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Boiling(SpatialAnimation):
    name = "ai_boiling"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "Heat diffuses upward as buoyant bubbles grow, rise, and pop."

    def _initialise_effect(self, _parameters):
        self.neighbors = []
        for index, point in enumerate(self.positions):
            nearest = sorted(
                (candidate for candidate in range(self.led_count) if candidate != index),
                key=lambda candidate: _distance(point, self.positions[candidate]),
            )[:5]
            self.neighbors.append(nearest)
        self.temperature = [0.0] * self.led_count
        self.bubbles = []
        self.substep = 1 / 60
        self.cooling = 0.055
        self.diffusion = 0.7
        self.bubble_limit = 30
        for _ in range(10):
            self._spawn_bubble()

    def _spawn_bubble(self):
        bottom = [index for index, point in enumerate(self.positions) if point[2] < self.height * 0.18]
        if bottom:
            index = self.generator.choice(bottom)
            self.bubbles.append({"index": index, "age": 0.0, "life": self.generator.uniform(2.0, 4.0), "radius": self.generator.uniform(0.12, 0.22)})
            self.temperature[index] = 1.0

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            updated = []
            for index, value in enumerate(self.temperature):
                neighbor_average = sum(self.temperature[n] for n in self.neighbors[index]) / max(1, len(self.neighbors[index]))
                bottom_heat = (0.9 if math.sin(self.elapsed * 1.8 + index * 2.1) > -0.25 else 0.12) if self.positions[index][2] < self.height * 0.2 else 0.0
                updated.append(max(0.0, min(1.0, value + (self.diffusion * (neighbor_average - value) + bottom_heat - self.cooling * value) * step)))
            self.temperature = updated
            remaining -= step
        if self.generator.random() < delta * 7.0 and len(self.bubbles) < self.bubble_limit:
            self._spawn_bubble()
        for bubble in self.bubbles:
            bubble["age"] += delta
        self.bubbles = [bubble for bubble in self.bubbles if bubble["age"] < bubble["life"]]
        frame = []
        for index, point in enumerate(self.positions):
            heat = self.temperature[index]
            color = _rgb(0.02 + 0.09 * heat, 0.95, 0.15 + 0.85 * heat)
            brightness = min(1.0, heat * 1.5)
            for bubble in self.bubbles:
                center = self.positions[bubble["index"]]
                center = (center[0], center[1], center[2] + bubble["age"] * self.height * 0.7)
                glow = max(0.0, 1 - _distance(point, center) / bubble["radius"])
                brightness = max(brightness, glow)
            frame.append(tuple(round(channel * brightness) for channel in color))
        return frame