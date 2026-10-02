PIXEL_ORDERS = ("RGB", "RBG", "GRB", "GBR", "BRG", "BGR")


class SimulatedStrip:
    def __init__(self, led_count, pixel_order="GRB"):
        self.led_count = led_count
        self.pixel_order = pixel_order
        self.color = (0, 0, 0)
        print(
            f"Simulating {led_count} LEDs using {pixel_order}; "
            "no hardware will be changed."
        )

    def fill(self, color):
        self.color = color
        print(
            f"Simulated {self.led_count} LEDs set to "
            f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"
        )

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

    def clear(self):
        self.fill((0, 0, 0))

    def close(self):
        self.clear()
        self.pixels.deinit()