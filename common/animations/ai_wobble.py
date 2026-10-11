import math

from common.animations.ai_base import SpatialAnimation, _rgb, _smooth


class Wobble(SpatialAnimation):
    name = "ai_wobble"
    author = "Carlos Gil & AI"
    description = "An elliptical vertical color sheet expands, turns, and contracts through the tree."

    def _initialise_effect(self, _parameters):
        profile_window = max(self.height * 0.05, 1e-6)
        self.tree_edges = []
        for _x, _y, z in self.positions:
            local_edge = max(
                math.hypot(other_x, other_y)
                for other_x, other_y, other_z in self.positions
                if abs(other_z - z) <= profile_window
            )
            self.tree_edges.append(max(local_edge, self.tree_radius * 0.04, 1e-6))
        self.edge_width = max(self.tree_radius * 0.035, self._estimate_led_spacing())
        self._start_cycle()

    def _start_cycle(self):
        self.base_hue = self.generator.random()
        self.hue_speed = self.generator.uniform(0.025, 0.12)
        self.start_angle = self.generator.uniform(0.0, 2 * math.pi)
        self.rotation_speed = self.generator.choice((-1.0, 1.0)) * self.generator.uniform(0.12, 0.48)
        self.expand_duration = self.generator.uniform(1.2, 2.8)
        self.contract_duration = self.generator.uniform(1.0, 2.4)
        self.cycle_elapsed = 0.0
        self.phase = "expanding"
        self.expansion = 0.0

    def _advance_wobble(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0.0:
            duration = self.expand_duration if self.phase == "expanding" else self.contract_duration
            phase_remaining = duration - self.cycle_elapsed
            step = min(remaining, phase_remaining)
            self.cycle_elapsed += step
            remaining -= step

            if self.phase == "expanding":
                self.expansion = min(1.0, self.cycle_elapsed / self.expand_duration)
            else:
                self.expansion = max(0.0, 1.0 - self.cycle_elapsed / self.contract_duration)

            if self.cycle_elapsed >= duration:
                if self.phase == "expanding":
                    self.phase = "contracting"
                    self.cycle_elapsed = 0.0
                    self.expansion = 1.0
                else:
                    self._start_cycle()

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta_seconds):
        self._advance_wobble(delta_seconds)
        plane_angle = self.start_angle + self.elapsed * self.rotation_speed
        if self.phase == "contracting":
            plane_angle += math.pi / 2
        normal_x = -math.sin(plane_angle)
        normal_y = math.cos(plane_angle)
        hue = (self.base_hue + self.elapsed * self.hue_speed) % 1.0
        color = _rgb(hue, 0.9, 1.0)
        frame = []

        for (x, y, z), tree_edge in zip(self.positions, self.tree_edges):
            vertical_offset = (z - self.height * 0.5) / (self.height * 0.58)
            ellipse_width = math.sqrt(max(0.0, 1.0 - vertical_offset * vertical_offset))
            half_width = tree_edge * 1.2 * ellipse_width * self.expansion
            side_distance = abs(x * normal_x + y * normal_y)
            edge_coverage = _smooth(
                (half_width + self.edge_width - side_distance) / self.edge_width
            )
            intensity = edge_coverage * ellipse_width
            frame.append(tuple(round(channel * intensity) for channel in color))
        return frame
