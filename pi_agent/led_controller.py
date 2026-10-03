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


class NeoPixelStrip:
    def __init__(self, led_count, pin_name, brightness, pixel_order):
        try:
            import board
            import neopixel
        except ImportError as error:
            raise RuntimeError(
                "Hardware mode requires Adafruit Blinka and CircuitPython NeoPixel; "
                "install pi_agent/requirements.txt on the Pi."
            ) from error

        pin = getattr(board, pin_name, None)
        order = getattr(neopixel, pixel_order, None)
        if pin is None:
            raise ValueError(f"Unknown board pin: {pin_name}")
        if order is None:
            raise ValueError(f"Unsupported pixel order: {pixel_order}")

        self.pixels = neopixel.NeoPixel(
            pin,
            led_count,
            brightness=brightness,
            auto_write=False,
            pixel_order=order,
        )

    def fill(self, color):
        self.pixels.fill(color)
        self.pixels.show()

    def set_one(self, index, color):
        if not 0 <= index < len(self.pixels):
            raise IndexError("LED index is outside the configured test range")
        self.pixels.fill((0, 0, 0))
        self.pixels[index] = color
        self.pixels.show()

    def set_frame(self, frame):
        if len(frame) != len(self.pixels):
            raise ValueError("Frame length must match the configured LED count")
        for index, color in enumerate(frame):
            self.pixels[index] = tuple(color)
        self.pixels.show()

    def clear(self):
        self.fill((0, 0, 0))

    def close(self):
        self.clear()
        self.pixels.deinit()