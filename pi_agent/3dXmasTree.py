#!/usr/bin/env python3

import argparse
import importlib
import inspect
import json
import math
import pkgutil
import sys
import threading
import time
from pathlib import Path

PI_AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PI_AGENT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PI_AGENT_DIR))

from common.Xmas_shared import require_platform, start_exit_key_monitor
from common.animations import Animation
from led_controller import NeoPixelStrip, SimulatedStrip


def discover_animations():
    import common.animations as animation_package

    discovered = {}
    failures = []
    for module_info in pkgutil.walk_packages(
        animation_package.__path__,
        prefix=f"{animation_package.__name__}.",
    ):
        try:
            module = importlib.import_module(module_info.name)
        except Exception as error:
            failures.append((module_info.name, str(error)))
            continue

        for candidate in vars(module).values():
            if (
                inspect.isclass(candidate)
                and candidate is not Animation
                and issubclass(candidate, Animation)
                and candidate.__module__ == module.__name__
                and not inspect.isabstract(candidate)
            ):
                if not candidate.name or candidate.name in discovered:
                    raise ValueError(f"Animation name is missing or duplicated: {candidate.name!r}")
                discovered[candidate.name] = candidate

    return [discovered[name] for name in sorted(discovered)], failures


def validate_frame(frame, led_count):
    colors = list(frame)
    if len(colors) != led_count:
        raise ValueError(
            f"Animation returned {len(colors)} LEDs; expected {led_count}"
        )

    validated = []
    for index, color in enumerate(colors):
        if len(color) != 3:
            raise ValueError(f"LED {index + 1} color must contain three RGB channels")
        channels = tuple(int(channel) for channel in color)
        if any(channel < 0 or channel > 255 for channel in channels):
            raise ValueError(f"LED {index + 1} RGB channels must be between 0 and 255")
        validated.append(channels)
    return validated


def run_animation(animation_class, strip, led_count, duration_seconds, fps, stop_event):
    animation = animation_class()
    initialized = False
    frames_rendered = 0
    try:
        animation.initialise(led_count, {})
        initialized = True
        started_at = time.monotonic()
        previous_frame_at = started_at
        next_frame_at = started_at
        frame_period = 1.0 / fps

        while not stop_event.is_set():
            now = time.monotonic()
            if now - started_at >= duration_seconds:
                break

            delta_seconds = max(0.0, now - previous_frame_at)
            previous_frame_at = now
            frame = validate_frame(animation.doframe(delta_seconds), led_count)
            strip.set_frame(frame)
            frames_rendered += 1

            next_frame_at += frame_period
            delay = next_frame_at - time.monotonic()
            if delay > 0:
                stop_event.wait(delay)
            else:
                next_frame_at = time.monotonic()
    finally:
        try:
            if initialized:
                animation.stop()
        finally:
            strip.clear()

    return frames_rendered


def main():
    require_platform("pi")
    parser = argparse.ArgumentParser(
        description="Cycle installed LED animations on the Raspberry Pi."
    )
    parser.add_argument("--hardware", action="store_true", help="Drive the physical LED strip.")
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--seconds-per-animation", type=float, default=None)
    parser.add_argument("--once", action="store_true", help="Run each animation once and exit.")
    parser.add_argument("--list-animations", action="store_true", help="List discovered animations and exit.")
    args = parser.parse_args()

    settings_path = PROJECT_ROOT / "common" / "settings.json"
    with settings_path.open("r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    animation_settings = settings.get("animation", {})
    fps = args.fps if args.fps is not None else animation_settings.get("fps", 30.0)
    seconds_per_animation = (
        args.seconds_per_animation
        if args.seconds_per_animation is not None
        else animation_settings.get("seconds_per_animation", 10.0)
    )
    if not math.isfinite(fps) or fps <= 0:
        parser.error("--fps must be a finite positive number")
    if not math.isfinite(seconds_per_animation) or seconds_per_animation <= 0:
        parser.error("--seconds-per-animation must be a finite positive number")

    animations, import_failures = discover_animations()
    for module_name, message in import_failures:
        print(f"Skipping {module_name}: {message}", file=sys.stderr)
    if not animations:
        parser.error("No importable Animation subclasses were found in common/animations")

    if args.list_animations:
        for animation_class in animations:
            print(
                f"{animation_class.name} v{animation_class.version} "
                f"by {animation_class.author}: {animation_class.description}"
            )
        return 0

    led_settings = settings["led"]
    led_count = led_settings.get("led_count")
    if args.hardware:
        if not isinstance(led_count, int) or led_count < 1:
            parser.error("Calibrate and save led.led_count before using --hardware")
    else:
        led_count = led_count or led_settings.get("capture_test_led_count", 100)
    pixel_order = led_settings.get("pixel_order") or "GRB"

    if args.hardware:
        strip = NeoPixelStrip(
            led_count,
            led_settings["pin"],
            led_settings["brightness"],
            pixel_order,
        )
    else:
        strip = SimulatedStrip(led_count, pixel_order)

    stop_event = threading.Event()
    exit_monitor = start_exit_key_monitor(stop_event.set)
    cycles_completed = 0
    print(
        f"Starting animation engine: {len(animations)} animations, {led_count} LEDs, "
        f"{fps:g} FPS target, {seconds_per_animation:g}s per animation "
        f"({'hardware' if args.hardware else 'simulation'}).",
        flush=True,
    )
    try:
        while not stop_event.is_set():
            for animation_class in animations:
                if stop_event.is_set():
                    break
                print(
                    f"Running {animation_class.name} v{animation_class.version} "
                    f"by {animation_class.author}.",
                    flush=True,
                )
                started_at = time.monotonic()
                frames_rendered = run_animation(
                    animation_class,
                    strip,
                    led_count,
                    seconds_per_animation,
                    fps,
                    stop_event,
                )
                elapsed = time.monotonic() - started_at
                if frames_rendered:
                    print(
                        f"{animation_class.name}: {frames_rendered} frames in "
                        f"{elapsed:.2f}s ({frames_rendered / max(elapsed, 1e-9):.1f} FPS).",
                        flush=True,
                    )
            cycles_completed += 1
            if args.once:
                break
    except KeyboardInterrupt:
        print("Keyboard interrupt; stopping animation engine.", flush=True)
    finally:
        stop_event.set()
        if exit_monitor is not None:
            exit_monitor.stop()
        strip.close()
        print("Animation engine stopped.", flush=True)

    return cycles_completed


if __name__ == "__main__":
    raise SystemExit(main())
