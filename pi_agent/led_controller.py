import re

print(f"led_controller loaded from {__file__}: hardware driver = rpi_ws281x")

PIXEL_ORDERS = ("RGB", "RBG", "GRB", "GBR", "BRG", "BGR")


class SimulatedStrip:
    def __init__(self, led_count, pixel_order="GRB"):
        self.led_count = led_count
        self.pixel_order = pixel_order
        self.color = (0, 0, 0)
        self.active_pixels = set()
        self.frame = [(0, 0, 0)] * led_count
        print(
            f"Simulating {led_count} LEDs using {pixel_order}; "
            "no hardware will be changed."
        )

    def fill(self, color):
        self.color = color
        self.frame = [color] * self.led_count
        self.active_pixels = (
            set(range(self.led_count)) if color != (0, 0, 0) else set()
        )
        print(
            f"Simulated {self.led_count} LEDs set to "
            f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        )

    def set_one(self, index, color):
        if not 0 <= index < self.led_count:
            raise IndexError("LED index is outside the configured test range")
        self.color = color
        self.frame = [(0, 0, 0)] * self.led_count
        self.frame[index] = color
        self.active_pixels = {index} if color != (0, 0, 0) else set()
        print(
            f"Simulated LED {index + 1} of {self.led_count} set to "
            f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        )

    def set_frame(self, frame):
        if len(frame) != self.led_count:
            raise ValueError("Frame length must match the configured LED count")
        self.frame = [tuple(color) for color in frame]
        self.active_pixels = {
            index for index, color in enumerate(self.frame) if color != (0, 0, 0)
        }
        self.color = self.frame[0]

    def clear(self):
        self.fill((0, 0, 0))

    def close(self):
        self.clear()


# GPIO -> PWM channel on Pi 4 and earlier.
PWM_CHANNELS = {12: 0, 18: 0, 13: 1, 19: 1}


# Model -> signal frequency in Hz (rpi_ws281x only drives 3-channel RGB strips here).
STRIP_MODELS = {
    "WS2811": 800000,
    "WS2812": 800000,
    "WS2812B": 800000,
    "SK6812": 800000,
    "WS2811_400K": 400000,
}
#DEFAULT_STRIP_MODEL = "WS2812B" # test strip model for GRB order and D13 pin
DEFAULT_STRIP_MODEL = "WS2812B" 


def _pack(color):
    return (int(color[0]) << 16) | (int(color[1]) << 8) | int(color[2])


class Ws281xStrip:
    def __init__(
        self,
        led_count,
        pin_name,
        brightness,
        pixel_order,
        strip_model=DEFAULT_STRIP_MODEL,
    ):
        try:
            from rpi_ws281x import PixelStrip, ws
        except ImportError as error:
            raise RuntimeError(
                "Hardware mode requires rpi_ws281x; "
                "install pi_agent/requirements.txt on the Pi."
            ) from error

        print(f"LED driver: rpi_ws281x, model {strip_model}, order {pixel_order}, pin {pin_name}, led count {led_count}, brightness {brightness}")
        match = re.fullmatch(r"D?(\d+)", str(pin_name))
        strip_type = getattr(ws, f"WS2811_STRIP_{pixel_order}", None)
        if strip_model not in STRIP_MODELS:
            raise ValueError(
                f"Unsupported strip model: {strip_model}; "
                f"choose from {', '.join(STRIP_MODELS)}"
            )
        if match is None:
            raise ValueError(f"Unknown GPIO pin: {pin_name}")
        if strip_type is None:
            raise ValueError(f"Unsupported pixel order: {pixel_order}")
        gpio = int(match.group(1))

        self.pixels = PixelStrip(
            led_count,
            gpio,
            freq_hz=STRIP_MODELS.get(strip_model, 800000),
            brightness=max(0, min(255, round(brightness * 255))),
            channel=PWM_CHANNELS.get(gpio, 0),
            strip_type=strip_type,
        )
        self.pixels.begin()
        self.led_count = led_count

    def fill(self, color):
        packed = _pack(color)
        for index in range(self.led_count):
            self.pixels.setPixelColor(index, packed)
        self.pixels.show()

    def set_one(self, index, color):
        if not 0 <= index < self.led_count:
            raise IndexError("LED index is outside the configured test range")
        for position in range(self.led_count):
            self.pixels.setPixelColor(position, 0)
        self.pixels.setPixelColor(index, _pack(color))
        self.pixels.show()

    def set_frame(self, frame):
        if len(frame) != self.led_count:
            raise ValueError("Frame length must match the configured LED count")
        for index, color in enumerate(frame):
            self.pixels.setPixelColor(index, _pack(color))
        self.pixels.show()

    def clear(self):
        self.fill((0, 0, 0))

    def close(self):
        self.clear()
