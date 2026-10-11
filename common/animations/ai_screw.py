import math

from common.animations.ai_base import SpatialAnimation, _rgb


class Screw(SpatialAnimation):
    name = "ai_screw"
    author = "Carlos Gil & AI"
    description = "A random-colored helix rises around the tree, then spins at full height."

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
        self.line_width = max(
            self.tree_radius * 0.08,
            self._estimate_led_spacing() * 1.5,
            self.height * 0.012,
        )
        self._start_cycle()

    def _start_cycle(self):
        self.color = _rgb(self.generator.random(), 0.95, 1.0)
        self.pitch = self.generator.uniform(2.5, 6.0)
        self.orientation = self.generator.uniform(0.0, 2 * math.pi)
        self.growth_speed = self.generator.uniform(0.3, 0.65) * self.height
        self.front_z = 0.0
        self.phase = "growing"
        self.spin_direction = self.generator.choice((-1.0, 1.0))
        self.spin_speed = self.generator.uniform(0.7, 2.0)
        self.spin_duration = self.generator.uniform(1.5, 4.0)
        self.spin_elapsed = 0.0
        self.spin_angle = 0.0

    def _advance_screw(self, delta_seconds):
        remaining = delta_seconds
        if self.phase == "growing":
            time_to_top = (self.height - self.front_z) / self.growth_speed
            if remaining < time_to_top:
                self.front_z += self.growth_speed * remaining
                return
            self.front_z = self.height
            self.phase = "spinning"
            remaining -= time_to_top

        if self.phase == "spinning" and remaining > 0.0:
            spin_time = min(remaining, self.spin_duration - self.spin_elapsed)
            self.spin_angle += self.spin_direction * self.spin_speed * spin_time
            self.spin_elapsed += spin_time
            if self.spin_elapsed >= self.spin_duration:
                self._start_cycle()

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta_seconds):
        self._advance_screw(delta_seconds)
        frame = []
        for (x, y, z), tree_edge in zip(self.positions, self.tree_edges):
            if z > self.front_z:
                frame.append((0, 0, 0))
                continue

            height_fraction = min(1.0, max(0.0, z / self.height))
            helix_angle = (
                self.orientation
                + 2 * math.pi * self.pitch * height_fraction
                + self.spin_angle
            )
            angle_difference = math.atan2(
                math.sin(math.atan2(y, x) - helix_angle),
                math.cos(math.atan2(y, x) - helix_angle),
            )
            helix_radius = tree_edge * 0.86
            distance = math.hypot(
                math.hypot(x, y) - helix_radius,
                angle_difference * helix_radius,
            )
            intensity = math.exp(-((distance / self.line_width) ** 2))
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame
