import math

from common.animations.ai_base import SpatialAnimation, _rgb


class Umbrella(SpatialAnimation):
    name = "ai_umbrella"
    author = "Carlos Gil & AI"
    description = "A colored conical canopy opens from the tree's central axis, then fades inward."

    EDGE_WIDTH = 0.12
    OPENING_EXTENT = 3.5

    def _initialise_effect(self, _parameters):
        self.virtual_vertex_z = self.height
        profile_window = max(self.virtual_vertex_z * 0.05, 1e-6)
        self.radial_positions = []
        for x, y, z in self.positions:
            local_edge = max(
                math.hypot(other_x, other_y)
                for other_x, other_y, other_z in self.positions
                if abs(other_z - z) <= profile_window
            )
            local_edge = max(local_edge, self.tree_radius * 0.04, 1e-6)
            self.radial_positions.append(math.hypot(x, y) / local_edge)
        self._start_cycle()

    def _start_cycle(self):
        self.color = _rgb(self.generator.random(), 0.95, 1.0)
        self.phase = "opening"
        self.canopy_radius = 0.0
        self.open_speed = self.generator.uniform(0.35, 0.7)
        self.close_speed = self.generator.uniform(0.45, 0.9)

    def _advance_canopy(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0.0:
            if self.phase == "opening":
                distance = self.OPENING_EXTENT - self.canopy_radius
                speed = self.open_speed
            elif self.phase == "holding":
                if remaining < self.hold_remaining:
                    self.hold_remaining -= remaining
                    break
                remaining -= self.hold_remaining
                self.hold_remaining = 0.0
                self.phase = "closing"
                continue
            else:
                distance = self.canopy_radius
                speed = self.close_speed

            time_to_transition = distance / speed
            if remaining < time_to_transition:
                change = speed * remaining
                self.canopy_radius += change if self.phase == "opening" else -change
                break

            self.canopy_radius = self.OPENING_EXTENT if self.phase == "opening" else 0.0
            remaining -= time_to_transition
            if self.phase == "opening":
                self.phase = "holding"
                self.hold_remaining = self.generator.uniform(0.6, 1.2)
            else:
                self._start_cycle()

    @staticmethod
    def _smooth(value):
        value = min(1.0, max(0.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _render_frame(self, delta_seconds):
        self._advance_canopy(delta_seconds)
        frame = []
        for radial_position in self.radial_positions:
            if self.phase == "opening":
                intensity = self._smooth(
                    (self.canopy_radius - radial_position) / self.EDGE_WIDTH
                )
            else:
                fade_distance = radial_position - self.canopy_radius
                intensity = 1.0 - self._smooth(fade_distance / self.EDGE_WIDTH)

            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame