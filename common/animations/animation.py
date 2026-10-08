import json
import math
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path


RGBColor = tuple[int, int, int]
LEDColor = RGBColor
LEDFrame = Sequence[RGBColor]


class Animation(ABC):
    """Shared lifecycle contract for Pi animations and the PC simulator."""

    name = "Unnamed animation"
    author = "Unknown"
    version = "0.1.0"
    description = "An LED animation that produces RGB frames over time."

    # Utility methods for reading and validating animation parameters.

    # Reads a numeric range from the raw value, ensuring it falls within the specified bounds.
    @staticmethod
    def _read_range(raw_value, name, lower_bound, upper_bound, minimum_exclusive=False):
        if (
            not isinstance(raw_value, Sequence)
            or isinstance(raw_value, (str, bytes))
            or len(raw_value) != 2
        ):
            raise ValueError(f"{name} must contain two numbers")
        values = tuple(float(value) for value in raw_value)
        minimum, maximum = values
        minimum_valid = minimum > lower_bound if minimum_exclusive else minimum >= lower_bound
        if (
            not all(math.isfinite(value) for value in values)
            or not minimum_valid
            or maximum > upper_bound
            or minimum > maximum
        ):
            raise ValueError(f"{name} values are outside the allowed range")
        return values

    # Reads a unit interval (0 to 1) from the raw value, ensuring it is valid.
    @staticmethod
    def _read_unit_interval(raw_value, name):
        if isinstance(raw_value, bool):
            raise ValueError(f"{name} must be between 0 and 1")
        value = float(raw_value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
        return value

    # Persists the effect parameters to a sidecar JSON file, ensuring atomic writes.
    @classmethod
    def _persist_effect_parameters(cls, parameters):
        sidecar_path = cls.PARAMETER_SIDECAR
        json_parameters = json.loads(json.dumps(parameters))
        try:
            current_parameters = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            current_parameters = None
        if current_parameters == json_parameters:
            return

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=sidecar_path.parent,
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(parameters, temporary_file, indent=2)
                temporary_file.write("\n")
            os.replace(temporary_path, sidecar_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    # Reads the LED positions from the raw value, falling back to a default layout if necessary.
    @classmethod
    def _read_positions(cls, raw_positions, led_count):
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
        return cls._fallback_positions(led_count)


    @staticmethod
    def _fallback_positions(led_count):
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions
    
    # Estimates the average spacing between LEDs, using a fallback if necessary.
    def _estimate_led_spacing(self, fallback=None):
        if fallback is None:
            fallback = self.height / 10
        if len(self.positions) < 2:
            return fallback
        distances = [
            math.sqrt(sum((first[axis] - second[axis]) ** 2 for axis in range(3)))
            for first, second in zip(self.positions, self.positions[1:])
        ]
        positive_distances = [distance for distance in distances if distance > 0]
        return sum(positive_distances) / len(positive_distances) if positive_distances else fallback

    # Abstract methods that must be implemented by concrete animation classes.
    @abstractmethod
    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        """Prepare state for a strip of led_count LEDs."""

    # Performs any necessary cleanup when the animation is stopped.
    @abstractmethod
    def doframe(self, delta_seconds: float) -> LEDFrame:
        """Return the RGB colors for the next frame."""

    # Stops the animation, releasing any resources and marking it as no longer running.
    def stop(self) -> None:
        """Release animation-owned resources and state."""
        self.running = False


__all__ = ["Animation", "LEDColor", "RGBColor", "LEDFrame"]
