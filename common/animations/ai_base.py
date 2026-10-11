import colorsys
import math
import random
from abc import ABC, abstractmethod
from collections.abc import Mapping

from common.animations import Animation, LEDFrame

# Helper functions for color manipulation, mixing, smoothing, and distance calculation.

# Convert HSV color to RGB color.
def _rgb(hue, saturation=0.9, value=1.0):
    """
    Converts an HSV color to an RGB color.

    Args:
        hue: The hue component of the color (0.0 to 1.0).
        saturation: The saturation component of the color (0.0 to 1.0).
        value: The value component of the color (0.0 to 1.0).

    Returns:
        A tuple representing the RGB color, with each channel in the range 0-255.
    """
    return tuple(
        round(channel * 255)
        for channel in colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    )


# Mix two RGB colors by a given amount.
def _mix(first, second, amount):
    """
    Mixes two RGB colors by a given amount.

    Args:
        first: The first RGB color as a tuple of three integers (0-255).
        second: The second RGB color as a tuple of three integers (0-255).
        amount: The mixing amount (0.0 to 1.0), where 0.0 returns the first color and 1.0 returns the second color.

    Returns:
        A tuple representing the mixed RGB color.
    """
    return tuple(round(a + (b - a) * amount) for a, b in zip(first, second))


# Smooth a value to ease in and out.
def _smooth(value):
    """
    Smooths a value to ease in and out.

    Args:
        value: The input value to smooth (0.0 to 1.0).

    Returns:
        The smoothed value.
    """
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


# Calculate the Euclidean distance between two RGB colors.
def _distance(first, second):
    """
    Calculates the Euclidean distance between two RGB colors.

    Args:
        first: The first RGB color as a tuple of three integers (0-255).
        second: The second RGB color as a tuple of three integers (0-255).

    Returns:
        The Euclidean distance between the two colors.
    """
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class SpatialAnimation(Animation, ABC):
    """Shared calibrated-position handling for the bundled showcase effects."""

    @abstractmethod
    def _initialise_effect(self, parameters):
        raise NotImplementedError

    @abstractmethod
    def _render_frame(self, delta_seconds):
        raise NotImplementedError

    def initialise(self, led_count: int, parameters: Mapping[str, object]) -> None:
        """
        Initializes the spatial state for the animation, including LED positions and tree dimensions.

        Args:
            led_count: The number of LEDs in the animation.
            parameters: The effect-specific parameters.
        """
        self._initialise_spatial_state(led_count, parameters)
        self._initialise_effect(parameters)

    def _initialise_spatial_state(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        """
        Initializes the spatial state for the animation, including LED positions and tree dimensions.

        Args:
            led_count: The number of LEDs in the animation.
            parameters: The effect-specific parameters.
        Raises:
            ValueError: If led_count is not positive or if tree dimensions are invalid.
        """
        if led_count < 1:
            raise ValueError("led_count must be positive")
        self.led_count = led_count
        self.generator = random.Random()
        positions = self._read_positions(parameters.get("positions"), led_count)

        minimum_z = min(position[2] for position in positions)
        maximum_z = max(position[2] for position in positions)
        self.center_z = (minimum_z + maximum_z) / 2
        radial_extent = max(math.hypot(x, y) for x, y, _z in positions)
        tree_height = parameters.get("tree_height_mm")
        tree_radius = parameters.get("tree_radius_mm")
        if tree_height is not None:
            tree_height = float(tree_height)
            if not math.isfinite(tree_height) or tree_height <= 0:
                raise ValueError("tree_height_mm must be finite and positive")
        if tree_radius is not None:
            tree_radius = float(tree_radius)
            if not math.isfinite(tree_radius) or tree_radius <= 0:
                raise ValueError("tree_radius_mm must be finite and positive")

        tree_height = tree_height or maximum_z - minimum_z
        tree_radius = tree_radius or radial_extent
        self.scale = max(tree_height, tree_radius * 2, 1e-6)
        self.positions = [
            (x / self.scale, y / self.scale, (z - minimum_z) / self.scale)
            for x, y, z in positions
        ]
        self.height = max(tree_height / self.scale, 1e-6)
        self.tree_radius = tree_radius / self.scale
        self.elapsed = 0.0
        self.running = True

    def doframe(self, delta_seconds: float) -> LEDFrame:
        """
        Renders the next frame of the animation.

        Args:
            delta_seconds: The time elapsed since the last frame, in seconds.

        Returns:
            The RGB colors for the next frame as a list of tuples.

        Raises:
            ValueError: If delta_seconds is not finite or is negative.
        """
        if not self.running:
            return [(0, 0, 0)] * self.led_count
        if not math.isfinite(delta_seconds) or delta_seconds < 0:
            raise ValueError("delta_seconds must be finite and non-negative")
        self.elapsed += delta_seconds
        frame = list(self._render_frame(delta_seconds))
        if len(frame) != self.led_count:
            raise ValueError(f"Animation returned {len(frame)} LEDs; expected {self.led_count}")
        return frame

