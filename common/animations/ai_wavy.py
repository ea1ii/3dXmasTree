import colorsys
import math

from common.animations.ai_base import SpatialAnimation


class Wavy(SpatialAnimation):
    name = "ai_wavy"
    author = "Carlos Gil & AI"
    version = "0.1.0"
    description = "A full-tree color pattern crossed by a drifting sinusoidal light wave."

    DIRECTION_DRIFT_RANGE = (5.0, 12.0)
    WAVE_SPEED_RANGE = (0.18, 0.42)
    SPATIAL_CYCLES_RANGE = (1.0, 4.0)

    def _initialise_effect(self, _parameters):
        self.pattern_mode = self.generator.choice(("solid", "gradient"))
        if self.pattern_mode == "solid":
            self.solid_color = self._hue_color(self.generator.random())
            self.gradient_colors = None
        else:
            stop_count = self.generator.randint(2, 5)
            self.gradient_colors = [
                self._hue_color(self.generator.random())
                for _ in range(stop_count)
            ]
            self.solid_color = None
            self.gradient_direction = self._random_unit_vector()
            gradient_projection = [
                sum(position[axis] * self.gradient_direction[axis] for axis in range(3))
                for position in self.positions
            ]
            self.gradient_minimum = min(gradient_projection)
            self.gradient_range = max(max(gradient_projection) - self.gradient_minimum, 1e-9)

        self.wave_direction = self._random_unit_vector()
        self.target_direction = self._random_unit_vector()
        self.direction_elapsed = 0.0
        self.direction_duration = self.generator.uniform(*self.DIRECTION_DRIFT_RANGE)
        self.spatial_cycles = self.generator.uniform(*self.SPATIAL_CYCLES_RANGE)
        self.wave_speed = self.generator.uniform(*self.WAVE_SPEED_RANGE)
        self.phase = self.generator.uniform(0.0, 2 * math.pi)

    @staticmethod
    def _hue_color(hue):
        return tuple(
            round(channel * 255)
            for channel in colorsys.hsv_to_rgb(hue % 1.0, 0.88, 1.0)
        )

    def _random_unit_vector(self):
        vertical = self.generator.uniform(-1.0, 1.0)
        azimuth = self.generator.uniform(0.0, 2 * math.pi)
        horizontal = math.sqrt(1.0 - vertical * vertical)
        return (
            horizontal * math.cos(azimuth),
            horizontal * math.sin(azimuth),
            vertical,
        )

    @staticmethod
    def _normalize(vector):
        length = math.sqrt(sum(component * component for component in vector))
        if length <= 1e-9:
            return (0.0, 0.0, 1.0)
        return tuple(component / length for component in vector)

    @staticmethod
    def _interpolate_color(first, second, amount):
        return tuple(
            round(start + (end - start) * amount)
            for start, end in zip(first, second)
        )

    def _color_at(self, position):
        if self.pattern_mode == "solid":
            return self.solid_color
        projection = sum(
            position[axis] * self.gradient_direction[axis]
            for axis in range(3)
        )
        gradient_position = min(
            1.0,
            max(0.0, (projection - self.gradient_minimum) / self.gradient_range),
        ) * (len(self.gradient_colors) - 1)
        stop = min(int(gradient_position), len(self.gradient_colors) - 2)
        return self._interpolate_color(
            self.gradient_colors[stop],
            self.gradient_colors[stop + 1],
            gradient_position - stop,
        )

    def _advance_direction(self, delta_seconds):
        remaining = delta_seconds
        while remaining > 0:
            time_left = self.direction_duration - self.direction_elapsed
            step = min(remaining, time_left)
            self.direction_elapsed += step
            remaining -= step
            progress = min(1.0, self.direction_elapsed / self.direction_duration)
            eased = progress * progress * (3 - 2 * progress)
            blended = tuple(
                start + (end - start) * eased
                for start, end in zip(self.wave_direction, self.target_direction)
            )
            self.wave_direction = self._normalize(blended)
            if self.direction_elapsed >= self.direction_duration:
                self.wave_direction = self.target_direction
                self.target_direction = self._random_unit_vector()
                self.direction_elapsed = 0.0
                self.direction_duration = self.generator.uniform(*self.DIRECTION_DRIFT_RANGE)

    def _render_frame(self, delta_seconds):
        self._advance_direction(delta_seconds)
        projections = [
            sum(position[axis] * self.wave_direction[axis] for axis in range(3))
            for position in self.positions
        ]
        minimum = min(projections)
        span = max(max(projections) - minimum, 1e-9)
        frame = []
        for position, projection in zip(self.positions, projections):
            wave_position = (projection - minimum) / span
            brightness = 0.5 + 0.5 * math.sin(
                2 * math.pi * (wave_position * self.spatial_cycles - self.elapsed * self.wave_speed)
                + self.phase
            )
            color = self._color_at(position)
            frame.append(tuple(round(channel * brightness) for channel in color))
        return frame