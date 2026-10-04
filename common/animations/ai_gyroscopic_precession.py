import math

from common.animations.ai_base import SpatialAnimation, _rgb


class GyroscopicPrecession(SpatialAnimation):
    name = "ai_gyroscopic_precession"
    author = "Carlos Gil & AI"
    version = "0.1.2"
    description = "A spinning rotor precesses under torque and slowly changes nutation."

    def _initialise_effect(self, _parameters):
        self.spin = self.generator.uniform(8.0, 15.0)
        self.mass = self.generator.uniform(0.6, 1.4)
        self.lever = self.generator.uniform(0.25, 0.55) * self.height
        self.inertia = self.generator.uniform(0.3, 0.8) * self.mass
        self.torque = self.mass * 2.4 * self.lever
        self.precession_rate = self.torque / (self.inertia * self.spin)
        self.precession_phase = self.generator.random() * 2 * math.pi
        self.nutation = self.generator.uniform(0.08, 0.28)
        self.nutation_rate = self.generator.uniform(0.25, 0.7)
        self.width = max(self.tree_radius * 0.24, 0.06)
        self.rotor_radius = self.tree_radius * 0.62
        self.rotor_width = max(self.tree_radius * 0.12, 0.03)
        self.color = _rgb(self.generator.uniform(0.52, 0.68), 0.85, 1)

    def _render_frame(self, _delta):
        precession = self.precession_phase + self.elapsed * self.precession_rate
        tilt = 0.45 + self.nutation * math.sin(self.elapsed * self.nutation_rate)
        axis = (math.sin(tilt) * math.cos(precession), math.sin(tilt) * math.sin(precession), math.cos(tilt))
        frame = []
        for x, y, z in self.positions:
            offset = (x, y, z - self.height * 0.5)
            along = sum(offset[i] * axis[i] for i in range(3))
            radial = math.sqrt(max(0.0, sum(value * value for value in offset) - along * along))
            ring_phase = along * 15 - self.elapsed * self.spin
            shaft = max(0.0, 1 - radial / self.width) * (0.55 + 0.45 * (0.5 + 0.5 * math.sin(ring_phase)))
            rotor = max(0.0, 1 - abs(radial - self.rotor_radius) / self.rotor_width) * max(0.0, 1 - abs(along) / (self.height * 0.12))
            intensity = max(shaft, rotor)
            frame.append(tuple(round(channel * intensity) for channel in self.color))
        return frame