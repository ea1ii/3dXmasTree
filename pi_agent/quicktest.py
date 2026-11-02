import time
import sys
from rpi_ws281x import PixelStrip, Color

LED_COUNT = 50       # test first 50 LEDs
LED_PIN = 18         # GPIO18 (pin 12)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 128
LED_INVERT = False
LED_CHANNEL = 0

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def clear():
    for i in range(LED_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

try:
    while True:
        for i in range(LED_COUNT):
            clear()
            strip.setPixelColor(i, Color(0, 255, 0))  # red
            strip.show()
            time.sleep(0.5)

except KeyboardInterrupt:
    clear()
    sys.exit(0)

