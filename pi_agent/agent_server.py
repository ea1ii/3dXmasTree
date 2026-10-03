#!/usr/bin/env python3

import argparse
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.Xmas_shared import require_platform

if __name__ == "__main__":
    require_platform("pi")

from common.agent_client import load_settings, save_settings
from common.Xmas_shared import start_exit_key_monitor
from led_controller import NeoPixelStrip, PIXEL_ORDERS, SimulatedStrip


TARGET_COLOR = (255, 128, 64)


class ColorTest:
    def __init__(self, settings, hardware):
        self.settings = settings
        self.hardware = hardware
        self.strip = None
        self.candidate_index = None

    def _apply_candidate(self, index):
        if self.strip is not None:
            self.strip.close()

        order = PIXEL_ORDERS[index]
        led_settings = self.settings["led"]
        if self.hardware:
            self.strip = NeoPixelStrip(
                led_settings["test_count"],
                led_settings["pin"],
                led_settings["brightness"],
                order,
            )
        else:
            self.strip = SimulatedStrip(led_settings["test_count"], order)

        self.candidate_index = index
        self.strip.fill(TARGET_COLOR)
        return self.status()

    def status(self):
        return {
            "pixel_order": PIXEL_ORDERS[self.candidate_index],
            "candidate_number": self.candidate_index + 1,
            "candidate_count": len(PIXEL_ORDERS),
            "target_color": "#FF8040",
            "test_count": self.settings["led"]["test_count"],
        }

    def start(self):
        if self.candidate_index is not None:
            raise RuntimeError("A color test is already running")
        count = self.settings["led"]["test_count"]
        if not isinstance(count, int) or not 1 <= count <= 10000:
            raise ValueError("led.test_count must be between 1 and 10000")
        return self._apply_candidate(0)

    def decide(self, decision):
        if self.candidate_index is None:
            raise RuntimeError("No color test is running")

        if decision == "no":
            return self._apply_candidate((self.candidate_index + 1) % len(PIXEL_ORDERS))
        if decision == "abort":
            self.stop()
            return {"decision": "abort"}
        if decision == "yes":
            self.settings["led"]["pixel_order"] = PIXEL_ORDERS[self.candidate_index]
            save_settings(self.settings)
            selected_order = PIXEL_ORDERS[self.candidate_index]
            self.stop()
            return {"decision": "yes", "pixel_order": selected_order}
        raise ValueError("decision must be yes, no, or abort")

    def stop(self):
        if self.strip is not None:
            self.strip.close()
            self.strip = None
        self.candidate_index = None


class LengthTest:
    def __init__(self, settings, hardware):
        self.settings = settings
        self.hardware = hardware
        self.strip = None
        self.current_led = None

    def start(self):
        if self.current_led is not None:
            raise RuntimeError("An LED length test is already running")
        led_settings = self.settings["led"]
        test_count = led_settings["test_count"]
        if not isinstance(test_count, int) or not 1 <= test_count <= 10000:
            raise ValueError("led.test_count must be between 1 and 10000")

        pixel_order = led_settings.get("pixel_order") or "GRB"
        if self.hardware:
            self.strip = NeoPixelStrip(
                test_count,
                led_settings["pin"],
                led_settings["brightness"],
                pixel_order,
            )
        else:
            self.strip = SimulatedStrip(test_count, pixel_order)

        self.current_led = 1
        self.strip.set_one(0, (255, 255, 255))
        return self.status()

    def status(self):
        return {
            "current_led": self.current_led,
            "test_count": self.settings["led"]["test_count"],
            "can_previous": self.current_led > 1,
            "can_next": self.current_led < self.settings["led"]["test_count"],
        }

    def next(self):
        if self.current_led is None:
            raise RuntimeError("No LED length test is running")
        if self.current_led >= self.settings["led"]["test_count"]:
            raise ValueError("Reached led.test_count; increase it to test farther")
        self.current_led += 1
        self.strip.set_one(self.current_led - 1, (255, 255, 255))
        return self.status()

    def previous(self):
        if self.current_led is None:
            raise RuntimeError("No LED length test is running")
        if self.current_led <= 1:
            raise ValueError("LED 1 is the first LED")
        self.current_led -= 1
        self.strip.set_one(self.current_led - 1, (255, 255, 255))
        return self.status()

    def done(self):
        if self.current_led is None:
            raise RuntimeError("No LED length test is running")
        led_count = self.current_led - 1
        self.settings["led"]["led_count"] = led_count
        save_settings(self.settings)
        self.stop()
        return {"decision": "done", "led_count": led_count}

    def abort(self):
        if self.current_led is None:
            raise RuntimeError("No LED length test is running")
        self.stop()
        return {"decision": "abort"}

    def stop(self):
        if self.strip is not None:
            self.strip.close()
            self.strip = None
        self.current_led = None


class PositionCaptureTest:
    def __init__(self, settings, hardware):
        self.settings = settings
        self.hardware = hardware
        self.strip = None
        self.current_led = None
        self.led_count = None

    def start(self):
        if self.current_led is not None:
            raise RuntimeError("A position capture loop is already running")
        led_settings = self.settings["led"]
        self.led_count = led_settings.get("capture_test_led_count", 5)
        if not isinstance(self.led_count, int) or not 1 <= self.led_count <= 10000:
            raise ValueError("led.capture_test_led_count must be between 1 and 10000")

        pixel_order = led_settings.get("pixel_order") or "GRB"
        if self.hardware:
            self.strip = NeoPixelStrip(
                self.led_count,
                led_settings["pin"],
                led_settings["brightness"],
                pixel_order,
            )
        else:
            self.strip = SimulatedStrip(self.led_count, pixel_order)

        self.current_led = 1
        self._show_current_led()
        return self.status()

    def _show_current_led(self):
        self.strip.set_one(self.current_led - 1, (255, 255, 255))
        print(
            f"Position capture: LED {self.current_led}/{self.led_count}",
            flush=True,
        )

    def status(self):
        return {"current_led": self.current_led, "led_count": self.led_count}

    def next(self):
        if self.current_led is None:
            raise RuntimeError("No position capture loop is running")
        if self.current_led >= self.led_count:
            raise ValueError("Already at the final test LED")
        self.current_led += 1
        self._show_current_led()
        return self.status()

    def stop(self):
        if self.strip is not None:
            self.strip.close()
            self.strip = None
        self.current_led = None
        self.led_count = None


def make_handler(color_test, token, length_test=None, position_test=None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status_code, body):
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _authorized(self):
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if not secrets.compare_digest(supplied, expected):
                self._send(401, {"error": "Unauthorized agent request"})
                return False
            return True

        def do_GET(self):
            if not self._authorized():
                return
            if self.path == "/health":
                self._send(200, {"agent": "pi", "ok": True})
                return
            self._send(404, {"error": "Unknown endpoint"})

        def do_POST(self):
            if not self._authorized():
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/color-test/start":
                    result = color_test.start()
                elif self.path == "/color-test/decision":
                    result = color_test.decide(payload.get("decision"))
                elif self.path == "/length-test/start" and length_test is not None:
                    result = length_test.start()
                elif self.path == "/length-test/next" and length_test is not None:
                    result = length_test.next()
                elif self.path == "/length-test/previous" and length_test is not None:
                    result = length_test.previous()
                elif self.path == "/length-test/done" and length_test is not None:
                    result = length_test.done()
                elif self.path == "/length-test/abort" and length_test is not None:
                    result = length_test.abort()
                elif self.path == "/position/start" and position_test is not None:
                    result = position_test.start()
                elif self.path == "/position/next" and position_test is not None:
                    result = position_test.next()
                elif self.path == "/position/stop" and position_test is not None:
                    position_test.stop()
                    result = {"stopped": True}
                elif self.path == "/shutdown":
                    result = {"shutdown": "requested"}
                    self._send(200, result)
                    print("Remote shutdown requested by command center.", flush=True)
                    threading.Thread(
                        target=self.server.shutdown,
                        daemon=True,
                    ).start()
                    return
                else:
                    self._send(404, {"error": "Unknown endpoint"})
                    return
            except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                self._send(400, {"error": str(error)})
                return
            except OSError as error:
                self._send(500, {"error": f"Could not save settings: {error}"})
                return
            self._send(200, result)

        def log_message(self, format_string, *args):
            print(f"{self.address_string()} - {format_string % args}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run the Pi LED command agent.")
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Drive the physical NeoPixel strip instead of simulating it.",
    )
    args = parser.parse_args()
    settings = load_settings()
    token_env = settings["agents"].get("token_env", "XMAS_AGENT_TOKEN")
    token = os.environ.get(token_env)
    if not token:
        parser.error(f"Set {token_env} before starting the agent")

    color_test = ColorTest(settings, args.hardware)
    length_test = LengthTest(settings, args.hardware)
    position_test = PositionCaptureTest(settings, args.hardware)
    address = ("0.0.0.0", settings["agents"]["pi"]["port"])
    server = ThreadingHTTPServer(
        address,
        make_handler(color_test, token, length_test, position_test),
    )
    print(f"Pi agent listening on port {address[1]} ({'hardware' if args.hardware else 'simulation'})")
    exit_monitor = start_exit_key_monitor(server.shutdown)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Keyboard interrupt; stopping Pi agent.", flush=True)
    finally:
        if exit_monitor is not None:
            exit_monitor.stop()
        color_test.stop()
        length_test.stop()
        position_test.stop()
        server.server_close()
        print("Pi agent stopped.", flush=True)


if __name__ == "__main__":
    main()