#!/usr/bin/env python3

import argparse
import json
import os
import secrets
import sys
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


def make_handler(color_test, token):
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
    address = ("0.0.0.0", settings["agents"]["pi"]["port"])
    server = ThreadingHTTPServer(address, make_handler(color_test, token))
    print(f"Pi agent listening on port {address[1]} ({'hardware' if args.hardware else 'simulation'})")
    exit_monitor = start_exit_key_monitor(server.shutdown)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        if exit_monitor is not None:
            exit_monitor.stop()
        color_test.stop()
        server.server_close()


if __name__ == "__main__":
    main()