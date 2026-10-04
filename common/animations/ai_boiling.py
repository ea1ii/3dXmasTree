import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Boiling(SpatialAnimation):
    name = "ai_boiling"
    author = "Carlos Gil & AI"
    version = "0.1.4"
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
        self.cooling = 0.28
        self.diffusion = 0.18
        self.bubble_limit = 30
        bottom = [index for index, point in enumerate(self.positions) if point[2] < self.height * 0.2]
        self.heater_phases = {
            self.generator.choice(bottom): self.generator.uniform(0.0, 2 * math.pi)
            for _ in range(min(4, len(bottom)))
        }
        self.top_indices = [
            index
            for index, point in enumerate(self.positions)
            if point[2] >= self.height * 0.94
        ]
        if not self.top_indices:
            self.top_indices = [max(range(self.led_count), key=lambda index: self.positions[index][2])]
        for _ in range(10):
            self._spawn_bubble()

    def _spawn_bubble(self):
        bottom = [index for index, point in enumerate(self.positions) if point[2] < self.height * 0.18]
        if bottom:
            index = self.generator.choice(bottom)
            origin = self.positions[index]
            rise_duration = self.generator.uniform(1.0, 2.2)
            rise_distance = max(0.0, self.height - origin[2])
            self.bubbles.append({
                "index": index,
                "origin": origin,
                "age": 0.0,
                "rise_duration": rise_duration,
                "rise_speed": rise_distance / rise_duration,
                "radius": self.generator.uniform(0.045, 0.09),
            })
            self.temperature[index] = 1.0

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            updated = []
            for index, value in enumerate(self.temperature):
                neighbor_average = sum(self.temperature[n] for n in self.neighbors[index]) / max(1, len(self.neighbors[index]))
                phase = self.heater_phases.get(index)
                bottom_heat = (
                    1.8 * max(0.0, math.sin(self.elapsed * 3.0 + phase))
                    if phase is not None
                    else 0.0
                )
                updated.append(max(0.0, min(1.0, value + (self.diffusion * (neighbor_average - value) + bottom_heat - self.cooling * value) * step)))
            self.temperature = updated
            remaining -= step
        if self.generator.random() < delta * 7.0 and len(self.bubbles) < self.bubble_limit:
            self._spawn_bubble()
        active_bubbles = []
        for bubble in self.bubbles:
            bubble["age"] += delta
            if bubble["age"] >= bubble["rise_duration"]:
                top_index = min(
                    self.top_indices,
                    key=lambda index: (
                        (self.positions[index][0] - bubble["origin"][0]) ** 2
                        + (self.positions[index][1] - bubble["origin"][1]) ** 2
                    ),
                )
                self.temperature[top_index] = 1.0
            else:
                active_bubbles.append(bubble)
        self.bubbles = active_bubbles
        frame = []
        for index, point in enumerate(self.positions):
            heat = self.temperature[index]
            color = _rgb(0.02 + 0.09 * heat, 0.95, 0.15 + 0.85 * heat)
            brightness = min(1.0, heat * 1.5)
            for bubble in self.bubbles:
                progress = min(1.0, bubble["age"] / bubble["rise_duration"])
                origin = bubble["origin"]
                center = (
                    origin[0],
                    origin[1],
                    min(self.height, origin[2] + bubble["rise_speed"] * bubble["age"]),
                )
                radius = bubble["radius"] * (1 + 1.7 * progress)
                glow = max(0.0, 1 - _distance(point, center) / radius)
                brightness = max(brightness, glow)
            frame.append(tuple(round(channel * brightness) for channel in color))
        return frame