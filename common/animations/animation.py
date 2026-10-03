from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence


RGBColor = tuple[int, int, int]
LEDColor = RGBColor
LEDFrame = Sequence[RGBColor]


class Animation(ABC):
    """Shared lifecycle contract for Pi animations and the PC simulator."""

    name = "Unnamed animation"
    author = "Unknown"
    version = "0.1.0"
    description = "An LED animation that produces RGB frames over time."

    @abstractmethod
    def initialise(
        self,
        led_count: int,
        parameters: Mapping[str, object],
    ) -> None:
        """Prepare state for a strip of led_count LEDs."""

    @abstractmethod
    def doframe(self, delta_seconds: float) -> LEDFrame:
        """Return the RGB colors for the next frame."""

    @abstractmethod
    def stop(self) -> None:
        """Release animation-owned resources and state."""


__all__ = ["Animation", "LEDColor", "RGBColor", "LEDFrame"]
