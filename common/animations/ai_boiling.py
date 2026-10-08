import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class Boiling(SpatialAnimation):
    name = "ai_boiling"
    author = "Carlos Gil & AI"
    version = "0.1.5"
    description = "Heat bubbles rise along the tree's LED branches and burst at the crown."

    def _initialise_effect(self, _parameters):
        self.neighbors = []
        for index, point in enumerate(self.positions):
            nearest = sorted(
                (candidate for candidate in range(self.led_count) if candidate != index),
                key=lambda candidate: _distance(point, self.positions[candidate]),
            )[:5]
            self.neighbors.append(nearest)
        self.upward_neighbors = []
        for index, point in enumerate(self.positions):
            higher = [
                candidate
                for candidate, candidate_point in enumerate(self.positions)
                if candidate_point[2] > point[2] + 1e-6
            ]
            higher.sort(key=lambda candidate: _distance(point, self.positions[candidate]))
            self.upward_neighbors.append(higher[:6])
        self.temperature = [0.0] * self.led_count
        self.pop_brightness = [0.0] * self.led_count
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
        if not bottom:
            return
        index = self.generator.choice(bottom)
        self.bubbles.append({
            "index": index,
            "age": 0.0,
            "move_remaining": 0.0,
            "move_interval": self.generator.uniform(0.08, 0.18),
            "radius": self.generator.uniform(0.8, 1.4) * max(self._estimate_led_spacing(), 0.025),
        })
        self.temperature[index] = 1.0

    def _pop_at_crown(self, source_index):
        origin = self.positions[source_index]
        top_index = min(
            self.top_indices,
            key=lambda index: (
                (self.positions[index][0] - origin[0]) ** 2
                + (self.positions[index][1] - origin[1]) ** 2
            ),
        )
        burst_indices = {top_index, *self.neighbors[top_index]}
        for index in burst_indices:
            self.temperature[index] = 1.0
            self.pop_brightness[index] = 1.0

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
            bubble["move_remaining"] -= delta
            while bubble["move_remaining"] <= 0:
                current_index = bubble["index"]
                if self.positions[current_index][2] >= self.height * 0.94:
                    self._pop_at_crown(current_index)
                    break
                candidates = self.upward_neighbors[current_index]
                if not candidates:
                    self._pop_at_crown(current_index)
                    break
                bubble["index"] = self.generator.choice(candidates)
                self.temperature[bubble["index"]] = 1.0
                bubble["move_remaining"] += bubble["move_interval"]
            else:
                active_bubbles.append(bubble)
        self.bubbles = active_bubbles
        self.pop_brightness = [max(0.0, value - delta * 2.2) for value in self.pop_brightness]
        frame = []
        for index, point in enumerate(self.positions):
            heat = self.temperature[index]
            color = _rgb(0.02 + 0.09 * heat, 0.95, 0.15 + 0.85 * heat)
            brightness = max(min(1.0, heat * 1.5), self.pop_brightness[index])
            for bubble in self.bubbles:
                center = self.positions[bubble["index"]]
                grow = min(1.0, bubble["age"] * 0.6)
                radius = bubble["radius"] * (1 + 0.7 * grow)
                glow = max(0.0, 1 - _distance(point, center) / radius)
                brightness = max(brightness, glow)
            frame.append(tuple(round(channel * brightness) for channel in color))
        return frame