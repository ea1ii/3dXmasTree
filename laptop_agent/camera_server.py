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

from common.agent_client import load_settings
from common.Xmas_shared import require_platform, start_exit_key_monitor

if __name__ == "__main__":
    require_platform("laptop")


def capture_jpeg(settings):
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "Install laptop_agent/requirements.txt to enable webcam capture"
        ) from error

    camera_settings = settings["camera"]
    camera = cv2.VideoCapture(camera_settings["device_index"])
    try:
        if not camera.isOpened():
            raise RuntimeError("Could not open the configured webcam")
        success, frame = camera.read()
        if not success:
            raise RuntimeError("The webcam did not return an image")
        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, camera_settings["jpeg_quality"]],
        )
        if not success:
            raise RuntimeError("Could not encode the webcam image")
        return encoded.tobytes()
    finally:
        camera.release()


def make_handler(settings, token):
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self):
            supplied = self.headers.get("Authorization", "")
            if not secrets.compare_digest(supplied, f"Bearer {token}"):
                self.send_error(401, "Unauthorized agent request")
                return False
            return True

        def do_GET(self):
            if not self._authorized():
                return
            if self.path == "/health":
                payload = json.dumps({"agent": "laptop", "ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path != "/capture":
                self.send_error(404, "Unknown endpoint")
                return

            try:
                image = capture_jpeg(settings)
            except RuntimeError as error:
                payload = json.dumps({"error": str(error)}).encode("utf-8")
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)

        def do_POST(self):
            if not self._authorized():
                return
            if self.path != "/shutdown":
                self.send_error(404, "Unknown endpoint")
                return

            payload = json.dumps({"shutdown": "requested"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            print("Remote shutdown requested by command center.", flush=True)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, format_string, *args):
            print(f"{self.address_string()} - {format_string % args}")

    return Handler


def main():
    print("Starting laptop camera agent...", flush=True)
    parser = argparse.ArgumentParser(description="Run the laptop webcam agent.")
    args = parser.parse_args()
    print("Loading shared settings...", flush=True)
    settings = load_settings()
    token_env = settings["agents"].get("token_env", "XMAS_AGENT_TOKEN")
    token = os.environ.get(token_env)
    if not token:
        parser.error(f"Set {token_env} before starting the agent")

    address = ("0.0.0.0", settings["agents"]["laptop"]["port"])
    print(f"Binding camera agent to port {address[1]}...", flush=True)
    server = ThreadingHTTPServer(address, make_handler(settings, token))
    exit_monitor = start_exit_key_monitor(server.shutdown)
    if exit_monitor is None:
        print(
            f"Running on port {address[1]}; this session has no interactive "
            "keyboard. Press Ctrl+C to exit.",
            flush=True,
        )
    else:
        print(
            f"Running on port {address[1]}; press Ctrl+Q or Ctrl+F4 "
            "(if forwarded by the terminal) to exit.",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        if exit_monitor is not None:
            exit_monitor.stop()
        server.server_close()
        print("Laptop camera agent stopped.", flush=True)


if __name__ == "__main__":
    main()