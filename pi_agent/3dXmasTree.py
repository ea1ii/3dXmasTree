#!/usr/bin/env python3

import argparse
import importlib
import inspect
import json
import math
import pkgutil
import random
import sys
import threading
import time
import traceback
from datetime import datetime
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


def load_animation_positions(led_count):
    frame_root = PROJECT_ROOT / "pc_agent" / "frames"
    position_files = sorted(
        frame_root.glob("*/positions_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in position_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_positions = payload["positions"]
            if len(raw_positions) != led_count:
                continue
            ordered_positions = sorted(
                raw_positions,
                key=lambda point: int(point.get("index", 0)),
            )
            positions = [
                (float(point["x"]), float(point["y"]), float(point["z"]))
                for point in ordered_positions
            ]
            if all(math.isfinite(value) for point in positions for value in point):
                return positions
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return None


def run_animation(
    animation_class,
    strip,
    led_count,
    duration_seconds,
    fps,
    stop_event,
    animation_parameters=None,
):
    animation = animation_class()
    initialized = False
    frames_rendered = 0
    try:
        animation.initialise(led_count, animation_parameters or {})
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


def execute_animation(
    animation_class,
    strip,
    led_count,
    duration_seconds,
    fps,
    stop_event,
    animation_parameters=None,
):
    try:
        frames_rendered = run_animation(
            animation_class,
            strip,
            led_count,
            duration_seconds,
            fps,
            stop_event,
            animation_parameters,
        )
    except Exception as error:
        print(
            f"Animation {animation_class.name} failed and will be skipped: {error}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc()
        return 0, error
    return frames_rendered, None


def scheduled_animation_duration(
    animation_class,
    default_duration,
    duration_override,
):
    if duration_override is not None:
        return duration_override
    return getattr(animation_class, "duration_seconds", default_duration)


def play_scheduled_animation(
    animation_class,
    strip,
    led_count,
    fps,
    default_duration,
    duration_override,
    stop_event,
    animation_parameters,
    failed_animations,
    deadline=None,
    timezone=None,
):
    if animation_class is None or animation_class.name in failed_animations:
        return

    duration = scheduled_animation_duration(
        animation_class,
        default_duration,
        duration_override,
    )
    if deadline is not None:
        remaining = (deadline - datetime.now(timezone)).total_seconds()
        duration = min(duration, max(0.0, remaining))
    if duration <= 0:
        return

    print(
        f"Running scheduled {animation_class.name} v{animation_class.version} "
        f"by {animation_class.author} for {duration:.1f}s.",
        flush=True,
    )
    started_at = time.monotonic()
    frames_rendered, animation_error = execute_animation(
        animation_class,
        strip,
        led_count,
        duration,
        fps,
        stop_event,
        animation_parameters,
    )
    if animation_error is not None:
        failed_animations.add(animation_class.name)
        return
    elapsed = time.monotonic() - started_at
    if frames_rendered:
        print(
            f"{animation_class.name}: {frames_rendered} frames in "
            f"{elapsed:.2f}s ({frames_rendered / max(elapsed, 1e-9):.1f} FPS).",
            flush=True,
        )


def run_night_schedule(
    animations,
    schedule,
    opening_animation,
    closing_animation,
    strip,
    led_count,
    fps,
    default_duration,
    duration_override,
    animation_parameters,
    stop_event,
    once=False,
):
    animation_by_name = {animation.name: animation for animation in animations}
    special_names = {name for name in (opening_animation, closing_animation) if name}
    regular_animations = [
        animation for animation in animations if animation.name not in special_names
    ]
    failed_animations = set()
    chooser = random.Random()
    announced_sunset = None

    while not stop_event.is_set():
        now = datetime.now(schedule.timezone)
        window, next_sunset = schedule.window_at(now)
        if window is None:
            strip.clear()
            wait_seconds = max(1.0, (next_sunset - now).total_seconds())
            if next_sunset != announced_sunset:
                print(
                    f"Daytime dormant; next scheduled sunset is {next_sunset.isoformat()}.",
                    flush=True,
                )
                announced_sunset = next_sunset
            stop_event.wait(min(wait_seconds, 60.0))
            continue

        announced_sunset = None
        night_start, night_end = window
        print(
            f"Night schedule active from {night_start.isoformat()} "
            f"to {night_end.isoformat()}.",
            flush=True,
        )
        if opening_animation:
            play_scheduled_animation(
                animation_by_name[opening_animation],
                strip,
                led_count,
                fps,
                default_duration,
                duration_override,
                stop_event,
                animation_parameters,
                failed_animations,
                deadline=night_end,
                timezone=schedule.timezone,
            )

        while not stop_event.is_set():
            now = datetime.now(schedule.timezone)
            if now >= night_end:
                break
            available = [
                animation
                for animation in regular_animations
                if animation.name not in failed_animations
            ]
            if not available:
                if len(failed_animations) >= len(animations):
                    print("All scheduled animations failed; stopping the Pi engine.", file=sys.stderr)
                    return
                stop_event.wait(min((night_end - now).total_seconds(), 60.0))
                continue
            play_scheduled_animation(
                chooser.choice(available),
                strip,
                led_count,
                fps,
                default_duration,
                duration_override,
                stop_event,
                animation_parameters,
                failed_animations,
                deadline=night_end,
                timezone=schedule.timezone,
            )

        if stop_event.is_set():
            break
        print(f"Night schedule ended at {night_end.isoformat()}.", flush=True)
        if opening_animation or closing_animation:
            strip.clear()
        if closing_animation:
            play_scheduled_animation(
                animation_by_name[closing_animation],
                strip,
                led_count,
                fps,
                default_duration,
                duration_override,
                stop_event,
                animation_parameters,
                failed_animations,
                timezone=schedule.timezone,
            )
        if once:
            break


def main():
    require_platform("pi")
    parser = argparse.ArgumentParser(
        description="Cycle installed LED animations on the Raspberry Pi."
    )
    parser.add_argument("--hardware", action="store_true", help="Drive the physical LED strip.")
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--seconds-per-animation", type=float, default=None)
    parser.add_argument(
        "--night-schedule",
        "--schedule",
        action="store_true",
        dest="night_schedule",
        help="Run opening, random night, and closing animations based on local sunrise/sunset.",
    )
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

    night_schedule = None
    opening_animation = ""
    closing_animation = ""
    if args.night_schedule:
        from night_schedule import NightSchedule

        schedule_settings = settings.get("night_schedule", {})
        try:
            night_schedule = NightSchedule(schedule_settings)
        except (TypeError, ValueError) as error:
            parser.error(str(error))

        animation_by_name = {animation.name: animation for animation in animations}
        for setting_name in ("opening_animation", "closing_animation"):
            animation_name = schedule_settings.get(setting_name, "")
            if animation_name is None:
                animation_name = ""
            if not isinstance(animation_name, str):
                parser.error(f"night_schedule.{setting_name} must be an animation name or blank")
            animation_name = animation_name.strip()
            if animation_name and animation_name not in animation_by_name:
                parser.error(
                    f"night_schedule.{setting_name} refers to unknown animation {animation_name!r}"
                )
            if setting_name == "opening_animation":
                opening_animation = animation_name
            else:
                closing_animation = animation_name

    led_settings = settings["led"]
    led_count = led_settings.get("led_count")
    if args.hardware:
        if not isinstance(led_count, int) or led_count < 1:
            parser.error("Calibrate and save led.led_count before using --hardware")
    else:
        led_count = led_count or led_settings.get("capture_test_led_count", 100)
    animation_positions = load_animation_positions(led_count)
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
    failed_animations = set()
    print(
        f"Starting animation engine: {len(animations)} animations, {led_count} LEDs, "
        f"{fps:g} FPS target, {seconds_per_animation:g}s per animation "
        f"({'hardware' if args.hardware else 'simulation'}).",
        flush=True,
    )
    try:
        if night_schedule is not None:
            run_night_schedule(
                animations,
                night_schedule,
                opening_animation,
                closing_animation,
                strip,
                led_count,
                fps,
                seconds_per_animation,
                args.seconds_per_animation,
                {"positions": animation_positions} if animation_positions else None,
                stop_event,
                once=args.once,
            )
        else:
            while not stop_event.is_set():
                for animation_class in animations:
                    if stop_event.is_set():
                        break
                    if animation_class.name in failed_animations:
                        continue
                    print(
                        f"Running {animation_class.name} v{animation_class.version} "
                        f"by {animation_class.author}.",
                        flush=True,
                    )
                    animation_duration = (
                        args.seconds_per_animation
                        if args.seconds_per_animation is not None
                        else getattr(animation_class, "duration_seconds", seconds_per_animation)
                    )
                    started_at = time.monotonic()
                    frames_rendered, animation_error = execute_animation(
                        animation_class,
                        strip,
                        led_count,
                        animation_duration,
                        fps,
                        stop_event,
                        {"positions": animation_positions} if animation_positions else None,
                    )
                    if animation_error is not None:
                        failed_animations.add(animation_class.name)
                        continue
                    elapsed = time.monotonic() - started_at
                    if frames_rendered:
                        print(
                            f"{animation_class.name}: {frames_rendered} frames in "
                            f"{elapsed:.2f}s ({frames_rendered / max(elapsed, 1e-9):.1f} FPS).",
                            flush=True,
                        )
                cycles_completed += 1
                if len(failed_animations) == len(animations):
                    print("All animations failed; stopping the Pi engine.", file=sys.stderr, flush=True)
                    break
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
