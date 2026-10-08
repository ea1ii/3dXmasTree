import math

from common.animations.ai_base import SpatialAnimation, _distance, _rgb


class ConvectionCells(SpatialAnimation):
    name = "ai_convection_cells"
    author = "Carlos Gil & AI"
    version = "0.1.3"
    description = "Hot and cool convection cells circulate through calibrated tree branches."

    def _initialise_effect(self, _parameters):
        self.neighbors = []
        self.upward_neighbors = []
        self.downward_neighbors = []
        for index, point in enumerate(self.positions):
            candidates = [candidate for candidate in range(self.led_count) if candidate != index]
            nearest = sorted(
                candidates,
                key=lambda candidate: _distance(point, self.positions[candidate]),
            )[:6]
            higher = sorted(
                (candidate for candidate in candidates if self.positions[candidate][2] > point[2] + 1e-6),
                key=lambda candidate: _distance(point, self.positions[candidate]),
            )[:4]
            lower = sorted(
                (candidate for candidate in candidates if self.positions[candidate][2] < point[2] - 1e-6),
                key=lambda candidate: _distance(point, self.positions[candidate]),
            )[:4]
            self.neighbors.append(nearest)
            self.upward_neighbors.append(higher)
            self.downward_neighbors.append(lower)

        self.temperature = [0.2 + 0.08 * (1 - point[2] / self.height) for point in self.positions]
        self.vertical_velocity = [0.0] * self.led_count
        self.cell_phases = [self.generator.uniform(0, 2 * math.pi) for _ in self.positions]
        bottom_indices = [index for index, point in enumerate(self.positions) if point[2] < self.height * 0.2]
        if not bottom_indices:
            bottom_indices = [min(range(self.led_count), key=lambda index: self.positions[index][2])]
        heater_indices = self.generator.sample(bottom_indices, min(10, len(bottom_indices)))
        self.heaters = {index: self.generator.uniform(0.8, 1.5) for index in heater_indices}
        self.substep = 1 / 60
        self.diffusion = 0.5
        self.buoyancy = 3.0
        self.drag = 0.9
        self.cooling = 0.2
        self.bubbles = []
        self.pop_brightness = [0.0] * self.led_count
        self.bubble_limit = 24
        self.bubble_spawn_remaining = 0.0
        self.top_indices = [index for index, point in enumerate(self.positions) if point[2] >= self.height * 0.94]
        if not self.top_indices:
            self.top_indices = [max(range(self.led_count), key=lambda index: self.positions[index][2])]
        self.led_spacing = self._estimate_led_spacing()

    def _spawn_bubble(self):
        bottom_indices = [index for index, point in enumerate(self.positions) if point[2] < self.height * 0.2]
        if not bottom_indices:
            bottom_indices = [min(range(self.led_count), key=lambda index: self.positions[index][2])]
        index = self.generator.choice(bottom_indices)
        self.bubbles.append({
            "index": index,
            "move_remaining": 0.0,
            "move_interval": self.generator.uniform(0.08, 0.18),
            "radius": self.generator.uniform(0.8, 1.5) * max(self.led_spacing, 0.025),
        })
        self.temperature[index] = 1.0

    def _pop_at_crown(self, source_index):
        origin = self.positions[source_index]
        crown_index = min(
            self.top_indices,
            key=lambda index: (
                (self.positions[index][0] - origin[0]) ** 2
                + (self.positions[index][1] - origin[1]) ** 2
            ),
        )
        for index in (crown_index, *self.neighbors[crown_index]):
            self.temperature[index] = 1.0
            self.pop_brightness[index] = 1.0

    def _render_frame(self, delta):
        remaining = delta
        while remaining > 0:
            step = min(remaining, self.substep)
            next_temperature = [0.0] * self.led_count
            next_velocity = [0.0] * self.led_count
            for index, temperature in enumerate(self.temperature):
                neighbors = self.neighbors[index]
                neighbor_average = sum(self.temperature[n] for n in neighbors) / max(1, len(neighbors))
                phase = self.cell_phases[index]
                heater = self.heaters.get(index, 0.0)
                source = heater * max(0.0, math.sin(self.elapsed * 2.4 + phase))
                conduction = self.diffusion * (neighbor_average - temperature)
                next_temperature[index] = min(
                    1.0,
                    max(0.04, temperature + (conduction + source - self.cooling * (temperature - 0.12)) * step),
                )
                acceleration = self.buoyancy * (temperature - 0.38) - self.drag * self.vertical_velocity[index]
                next_velocity[index] = max(-1.4, min(1.4, self.vertical_velocity[index] + acceleration * step))

            transport = [0.0] * self.led_count
            for index, velocity in enumerate(next_velocity):
                destinations = self.upward_neighbors[index] if velocity >= 0 else self.downward_neighbors[index]
                if not destinations:
                    continue
                destination = self.generator.choice(destinations[:min(3, len(destinations))])
                amount = min(next_temperature[index] * 0.3, abs(velocity) * step * 0.65)
                transport[index] -= amount
                transport[destination] += amount
            self.temperature = [
                min(1.0, max(0.04, next_temperature[i] + transport[i]))
                for i in range(self.led_count)
            ]
            self.vertical_velocity = next_velocity
            remaining -= step

        self.bubble_spawn_remaining -= delta
        if self.bubble_spawn_remaining <= 0 and len(self.bubbles) < self.bubble_limit:
            self._spawn_bubble()
            self.bubble_spawn_remaining = self.generator.uniform(0.12, 0.28)
        active_bubbles = []
        for bubble in self.bubbles:
            bubble["move_remaining"] -= delta
            while bubble["move_remaining"] <= 0:
                index = bubble["index"]
                if self.positions[index][2] >= self.height * 0.94 or not self.upward_neighbors[index]:
                    self._pop_at_crown(index)
                    break
                choices = self.upward_neighbors[index][:min(5, len(self.upward_neighbors[index]))]
                bubble["index"] = self.generator.choice(choices)
                self.temperature[bubble["index"]] = 1.0
                bubble["move_remaining"] += bubble["move_interval"]
            else:
                active_bubbles.append(bubble)
        self.bubbles = active_bubbles
        self.pop_brightness = [max(0.0, value - delta * 2.2) for value in self.pop_brightness]

        frame = []
        for index, (_x, _y, z) in enumerate(self.positions):
            heat = self.temperature[index]
            velocity = self.vertical_velocity[index]
            swirl = math.sin(self.elapsed * 1.4 - z * 8 + self.cell_phases[index])
            heat = min(1.0, heat + max(0.0, swirl * velocity) * 0.06)
            if velocity > 0.02:
                hue = 0.08 - 0.05 * heat
            else:
                hue = 0.55 + 0.08 * (1 - heat)
            intensity = min(1.0, 0.26 + 0.72 * heat + 0.06 * max(0.0, swirl))
            intensity = max(intensity, self.pop_brightness[index])
            color = _rgb(hue, 0.9, 1)
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame