import math

from common.animations.ai_base import SpatialAnimation, _rgb


class BouncingDisk(SpatialAnimation):
    name = "ai_bouncing_disk"
    author = "Carlos Gil & AI"
    description = "A spring-launched colored disk rises, pauses, then falls and bounces."

    def _initialise_effect(self, _parameters):
        self.substep = 1 / 120
        self.disk_thickness = max(
            self.height * 0.035,
            self._estimate_led_spacing() * 1.5,
        )
        self.bottom_z = self.disk_thickness
        self.top_z = max(self.bottom_z, self.height - self.disk_thickness)
        self._start_cycle()

    def _start_cycle(self):
        self.color = _rgb(self.generator.random(), 0.9, 1.0)
        self.mass = self.generator.uniform(0.6, 1.8)
        self.gravity = self.height * self.generator.uniform(1.3, 2.7)
        self.compression_height = self.top_z - self.bottom_z
        self.invisible_force = self.mass * self.height * self.generator.uniform(2.5, 5.0)
        self.spring_stiffness = (
            2.0
            * self.invisible_force
            / self.compression_height
            * self.generator.uniform(0.98, 1.0)
        )
        self.spring_compression = 0.0
        self.restitution = self.generator.uniform(0.65, 0.85)
        self.bounce_threshold = self.height * self.generator.uniform(0.025, 0.06)
        self.position_z = self.bottom_z
        self.velocity_z = 0.0
        self.phase = "compressing"
        self.top_hold = 0.0

    def _advance_disk(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0.0:
            step = min(remaining, self.substep)
            if self.phase == "compressing":
                self.spring_compression = min(
                    self.compression_height,
                    max(0.0, self.position_z - self.bottom_z),
                )
                spring_force = self.spring_stiffness * self.spring_compression
                acceleration = (self.invisible_force - spring_force) / self.mass
                self.velocity_z += acceleration * step
                self.position_z += self.velocity_z * step
                if self.position_z >= self.top_z:
                    self.position_z = self.top_z
                    self.spring_compression = self.compression_height
                    self.velocity_z = 0.0
                    self.top_hold = self.generator.uniform(0.8, 2.0)
                    self.phase = "holding"
            elif self.phase == "holding":
                self.top_hold -= step
                if self.top_hold <= 0.0:
                    self.phase = "falling"
            else:
                self.velocity_z -= self.gravity * step
                self.position_z += self.velocity_z * step
                if self.position_z <= self.bottom_z:
                    self.position_z = self.bottom_z
                    self.velocity_z = abs(self.velocity_z) * self.restitution
                    if self.velocity_z <= self.bounce_threshold:
                        self._start_cycle()
            remaining -= step

    def _render_frame(self, delta_seconds):
        self._advance_disk(delta_seconds)
        frame = []
        width = max(self.disk_thickness, 1e-6)
        for _x, _y, z in self.positions:
            distance = abs(z - self.position_z) / width
            intensity = math.exp(-(distance * distance))
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame
