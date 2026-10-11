import math

from common.animations.ai_base import SpatialAnimation, _rgb


class Fight(SpatialAnimation):
    name = "ai_fight"
    author = "Carlos Gil & AI"
    description = "Two shifting colored planes rotate through the tree and blend where they cross."

    def _initialise_effect(self, _parameters):
        self.pivot_z = self.generator.uniform(0.25, 0.75) * self.height
        self.plane_width = max(self.tree_radius * 0.045, self.height * 0.012)
        self.pivot_width = max(self.tree_radius * 0.12, self.height * 0.045)
        self.pivot_height = max(self.height * 0.12, 1e-6)
        self.planes = [self._new_plane() for _ in range(2)]

    def _new_plane(self):
        normal = self._random_unit_vector()
        candidate_axis = self._random_unit_vector()
        rotation_axis = self._cross(normal, candidate_axis)
        axis_length = math.sqrt(sum(component * component for component in rotation_axis))
        if axis_length < 1e-6:
            rotation_axis = self._cross(normal, (0.0, 0.0, 1.0))
            axis_length = math.sqrt(sum(component * component for component in rotation_axis))
        rotation_axis = tuple(component / axis_length for component in rotation_axis)
        return {
            "normal": normal,
            "rotation_axis": rotation_axis,
            "speed": self._random_rotation_speed(),
            "speed_change_in": self.generator.uniform(1.5, 4.0),
            "hue": self.generator.random(),
            "hue_speed": self.generator.choice((-1.0, 1.0))
            * self.generator.uniform(0.006, 0.025),
        }

    def _random_rotation_speed(self):
        return self.generator.uniform(0.16, 0.58)

    def _random_unit_vector(self):
        z = self.generator.uniform(-1.0, 1.0)
        angle = self.generator.uniform(0.0, 2 * math.pi)
        horizontal = math.sqrt(1.0 - z * z)
        return horizontal * math.cos(angle), horizontal * math.sin(angle), z

    @staticmethod
    def _cross(first, second):
        return (
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0],
        )

    @classmethod
    def _rotate_vector(cls, vector, axis, angle):
        cosine = math.cos(angle)
        sine = math.sin(angle)
        cross = cls._cross(axis, vector)
        dot = sum(component * axis_component for component, axis_component in zip(vector, axis))
        return tuple(
            component * cosine
            + cross_component * sine
            + axis_component * dot * (1.0 - cosine)
            for component, cross_component, axis_component in zip(vector, cross, axis)
        )

    def _advance_planes(self, delta_seconds):
        for plane in self.planes:
            remaining = delta_seconds
            while remaining > 0.0:
                step = min(remaining, plane["speed_change_in"])
                plane["normal"] = self._rotate_vector(
                    plane["normal"],
                    plane["rotation_axis"],
                    plane["speed"] * step,
                )
                plane["hue"] = (plane["hue"] + plane["hue_speed"] * step) % 1.0
                plane["speed_change_in"] -= step
                remaining -= step
                if plane["speed_change_in"] <= 0.0:
                    plane["speed"] = self._random_rotation_speed()
                    plane["speed_change_in"] = self.generator.uniform(1.5, 4.0)

    # Overrides SpatialAnimation._render_frame.
    def _render_frame(self, delta_seconds):
        self._advance_planes(delta_seconds)
        colors = [_rgb(plane["hue"], 0.9, 1.0) for plane in self.planes]
        frame = []

        for x, y, z in self.positions:
            relative = (x, y, z - self.pivot_z)
            radial_distance = math.hypot(x, y)
            pivot_glow = math.exp(
                -((radial_distance / self.pivot_width) ** 2)
                -(((z - self.pivot_z) / self.pivot_height) ** 2)
            )
            patch_extent = math.sqrt(
                (radial_distance / max(self.tree_radius * 1.25, 1e-6)) ** 2
                + ((z - self.pivot_z) / max(self.height * 0.72, 1e-6)) ** 2
            )
            patch_envelope = math.exp(-0.35 * patch_extent**4)
            intensities = []
            for plane in self.planes:
                plane_distance = abs(sum(
                    coordinate * normal_component
                    for coordinate, normal_component in zip(relative, plane["normal"])
                ))
                sheet_glow = math.exp(-((plane_distance / self.plane_width) ** 2))
                intensities.append(min(1.0, (sheet_glow + pivot_glow) * patch_envelope))

            total_intensity = sum(intensities)
            divisor = max(1.0, total_intensity)
            frame.append(
                tuple(
                    round(
                        sum(color[channel] * intensity for color, intensity in zip(colors, intensities))
                        / divisor
                    )
                    for channel in range(3)
                )
            )
        return frame
