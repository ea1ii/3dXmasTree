import colorsys
import math
import random
from collections.abc import Mapping, Sequence

from common.animations import Animation, LEDFrame


class CrazyPlaneAnimation(Animation):
    name = "crazy_plane"
    author = "Carlos Gil"
    version = "0.1.0"
    description = "Two colors split by a sweeping plane that rotates in 3D."

    BASE_NORMAL = (0.28, 0.36, 1.0)
    ANGULAR_SPEED_RANGE = (1.5, 4.0)
    ROTATION_CHANGE_RANGE = (0.25, 0.75)
    HUE_TRANSITION_RANGE = (2.0, 5.0)

    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        if led_count < 1:
            raise ValueError("led_count must be positive")

        self.led_count = led_count
        self.generator = random.Random()
        self.positions = self._read_positions(parameters.get("positions"), led_count)
        self.minimum_z = min(position[2] for position in self.positions)
        self.maximum_z = max(position[2] for position in self.positions)
        self.height = self.maximum_z - self.minimum_z
        if self.height <= 0:
            self.positions = self._fallback_positions(led_count)
            self.minimum_z = min(position[2] for position in self.positions)
            self.maximum_z = max(position[2] for position in self.positions)
            self.height = self.maximum_z - self.minimum_z
            if self.height <= 0:
                self.maximum_z = self.minimum_z + 1.0
                self.height = 1.0

        self.current_hue = self.generator.random()
        self.current_hue_separation = self.generator.uniform(1 / 3, 0.5)
        self.target_hue = self.generator.random()
        self.target_hue_separation = self.generator.uniform(1 / 3, 0.5)
        self.hue_transition_elapsed = 0.0
        self.hue_transition_duration = self.generator.uniform(*self.HUE_TRANSITION_RANGE)
        self.negative_color, self.positive_color = self._hue_pair(
            self.current_hue,
            self.current_hue_separation,
        )

        self.sweep_phase = self.height
        self.sweep_speed = self.height / self.generator.uniform(5.0, 9.0)
        self.speed_change_remaining = self.generator.uniform(0.4, 1.2)
        self.angles = [self.generator.uniform(-math.pi, math.pi) for _ in range(3)]
        self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
        self.rotation_change_remaining = self.generator.uniform(*self.ROTATION_CHANGE_RANGE)
        self.running = True

    @staticmethod
    def _read_positions(raw_positions, led_count):
        if isinstance(raw_positions, Sequence) and len(raw_positions) == led_count:
            try:
                positions = [
                    tuple(float(coordinate) for coordinate in position)
                    for position in raw_positions
                ]
                if all(
                    len(position) == 3
                    and all(math.isfinite(value) for value in position)
                    for position in positions
                ):
                    return positions
            except (TypeError, ValueError):
                pass
        return CrazyPlaneAnimation._fallback_positions(led_count)

    @staticmethod
    def _fallback_positions(led_count):
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions

    @staticmethod
    def _color_from_hue(hue):
        return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, 0.92, 1.0))

    def _hue_pair(self, hue, separation):
        return (
            self._color_from_hue(hue),
            self._color_from_hue((hue + separation) % 1.0),
        )

    def _advance_hues(self, delta_seconds):
        self.hue_transition_elapsed += delta_seconds
        if self.hue_transition_elapsed >= self.hue_transition_duration:
            self.current_hue = self.target_hue
            self.current_hue_separation = self.target_hue_separation
            self.target_hue = self.generator.random()
            self.target_hue_separation = self.generator.uniform(1 / 3, 0.5)
            self.hue_transition_elapsed = 0.0
            self.hue_transition_duration = self.generator.uniform(*self.HUE_TRANSITION_RANGE)

        progress = self.hue_transition_elapsed / self.hue_transition_duration
        eased_progress = progress * progress * (3 - 2 * progress)
        hue_delta = (self.target_hue - self.current_hue + 0.5) % 1.0 - 0.5
        hue = (self.current_hue + hue_delta * eased_progress) % 1.0
        separation = (
            self.current_hue_separation
            + (self.target_hue_separation - self.current_hue_separation) * eased_progress
        )
        self.negative_color, self.positive_color = self._hue_pair(hue, separation)

    def _random_angular_speed(self):
        sign = self.generator.choice((-1.0, 1.0))
        return sign * self.generator.uniform(*self.ANGULAR_SPEED_RANGE)

    def _plane_normal(self):
        x, y, z = self.BASE_NORMAL

        cosine = math.cos(self.angles[0])
        sine = math.sin(self.angles[0])
        y, z = y * cosine - z * sine, y * sine + z * cosine

        cosine = math.cos(self.angles[1])
        sine = math.sin(self.angles[1])
        x, z = x * cosine + z * sine, -x * sine + z * cosine

        cosine = math.cos(self.angles[2])
        sine = math.sin(self.angles[2])
        x, y = x * cosine - y * sine, x * sine + y * cosine

        magnitude = math.sqrt(x * x + y * y + z * z)
        return x / magnitude, y / magnitude, z / magnitude

    def doframe(self, delta_seconds: float) -> LEDFrame:
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")

        self._advance_hues(delta_seconds)

        self.speed_change_remaining -= delta_seconds
        if self.speed_change_remaining <= 0:
            self.sweep_speed = self.height / self.generator.uniform(5.0, 9.0)
            self.speed_change_remaining = self.generator.uniform(0.4, 1.2)

        self.rotation_change_remaining -= delta_seconds
        if self.rotation_change_remaining <= 0:
            self.angular_speeds = [self._random_angular_speed() for _ in range(3)]
            self.rotation_change_remaining = self.generator.uniform(*self.ROTATION_CHANGE_RANGE)

        for axis in range(3):
            self.angles[axis] = (
                self.angles[axis] + self.angular_speeds[axis] * delta_seconds
            ) % (2 * math.pi)

        sweep_period = 2.0 * self.height
        self.sweep_phase = (
            self.sweep_phase + self.sweep_speed * delta_seconds
        ) % sweep_period
        if self.sweep_phase <= self.height:
            plane_height = self.minimum_z + self.sweep_phase
        else:
            plane_height = self.minimum_z + sweep_period - self.sweep_phase

        normal_x, normal_y, normal_z = self._plane_normal()
        frame = []
        for x, y, z in self.positions:
            signed_distance = (
                x * normal_x + y * normal_y + (z - plane_height) * normal_z
            )
            frame.append(self.negative_color if signed_distance < 0 else self.positive_color)
        return frame

    def stop(self) -> None:
        self.running = False
