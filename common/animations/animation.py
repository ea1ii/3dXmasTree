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
        """
        Reads a numeric range from the raw value, ensuring it falls within the specified bounds.

        Args:
            raw_value: The raw input value to read.
            name: The name of the parameter (for error messages).
            lower_bound: The minimum allowed value.
            upper_bound: The maximum allowed value.
            minimum_exclusive: Whether the minimum value is exclusive.

        Returns:
            A tuple containing the validated minimum and maximum values.

        Raises:
            ValueError: If the raw value is not a valid range.
        """
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
        """
        Reads a unit interval (0 to 1) from the raw value, ensuring it is valid.

        Args:
            raw_value: The raw input value to read.
            name: The name of the parameter (for error messages).

        Returns:
            The validated unit interval value.

        Raises:
            ValueError: If the raw value is not a valid unit interval.
        """
        if isinstance(raw_value, bool):
            raise ValueError(f"{name} must be between 0 and 1")
        value = float(raw_value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
        return value
        
    # Loads the effect parameters, combining defaults, sidecar, and overrides.
    @classmethod
    def _load_effect_parameters(cls, parameters, effect_name, defaults, sidecar_path):
        """
        Loads the effect parameters, combining defaults, sidecar, and overrides.

        Args:
            parameters: The raw input parameters mapping.
            effect_name: The name of the effect to load parameters for.
            defaults: The default parameter values.
            sidecar_path: The path to the sidecar JSON file containing additional parameters.

        Returns:
            A dictionary containing the combined effect parameters.

        Raises:
            ValueError: If any of the input values are invalid.
        """
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be a mapping")
        try:
            sidecar_parameters = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            sidecar_parameters = {}
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid {effect_name} parameter sidecar: {error}") from error
        if not isinstance(sidecar_parameters, dict):
            raise ValueError(f"{effect_name} parameter sidecar must contain a JSON object")

        overrides = parameters.get(effect_name, {})
        if not isinstance(overrides, Mapping):
            raise ValueError(f"parameters[{effect_name!r}] must be a mapping")
        return {**defaults, **sidecar_parameters, **overrides}

    # Persists the effect parameters to a sidecar JSON file, ensuring atomic writes.
    @classmethod
    def _persist_effect_parameters(cls, parameters):
        """
        Persists the effect parameters to a sidecar JSON file, ensuring atomic writes.

        Args:
            parameters: The effect parameters to persist.

        Raises:
            ValueError: If the parameters cannot be persisted due to invalid JSON or file errors.
        """
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
        """
        Reads the LED positions from the raw value, falling back to a default layout if necessary.

        Args:
            raw_positions: The raw input positions to read.
            led_count: The number of LEDs to read positions for.

        Returns:
            A list of 3D positions for each LED.
        """
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
        """
        Generates a default layout of LED positions in 3D space.

        Args:
            led_count: The number of LEDs to generate positions for.

        Returns:
            A list of 3D positions for each LED.
        """
        positions = []
        for index in range(led_count):
            height = index / max(1, led_count - 1)
            angle = index * 2.399963229728653
            radius = 0.42 * (1.0 - height)
            positions.append((radius * math.cos(angle), radius * math.sin(angle), height))
        return positions
    
    # Estimates the average spacing between LEDs, using a fallback if necessary.
    def _estimate_led_spacing(self, fallback=None):
        """
        Estimates the average spacing between LEDs, using a fallback if necessary.

        Args:
            fallback: The fallback spacing to use if the average cannot be computed.

        Returns:
            The estimated average spacing between LEDs.
        """
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

    # Initializes shared animation state before dispatching to the effect hook.
    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
) -> None:
        """
        Initializes the shared animation state before dispatching to the effect hook.

        Args:
            led_count: The number of LEDs in the animation.
            parameters: The effect-specific parameters.

        Raises:
            ValueError: If led_count is not positive.
        """
        if led_count < 1:
            raise ValueError("led_count must be positive")
        self.led_count = led_count
        self._initialise_effect(parameters)
        self.running = True

    @abstractmethod
    def _initialise_effect(self, parameters: Mapping[str, object]) -> None:
        """Initialize effect-specific state after shared setup."""

    # Performs any necessary cleanup when the animation is stopped.
    @abstractmethod
    def doframe(self, delta_seconds: float) -> LEDFrame:
        """Return the RGB colors for the next frame."""

    # Stops the animation, releasing any resources and marking it as no longer running.
    def stop(self) -> None:
        """Release animation-owned resources and state."""
        self.running = False


__all__ = ["Animation", "LEDColor", "RGBColor", "LEDFrame"]
