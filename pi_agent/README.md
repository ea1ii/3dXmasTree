# Raspberry Pi LED agent

## Files

| File | Purpose |
| --- | --- |
| `agent_server.sh` | Launcher for the agent server: sets up the venv, stores the shared token, and starts `agent_server.py`. |
| `agent_server.py` | HTTP agent the command center calls for LED setup (color-order test and strip-length calibration); saves results to `common/settings.json`. |
| `led_controller.py` | LED strip drivers: `NeoPixelStrip` (hardware) and `SimulatedStrip`, plus the supported pixel orders. |
| `3dXmasTree.sh` | Launcher for the animation engine: sets up the venv and animation dependencies, then starts `3dXmasTree.py`. |
| `3dXmasTree.py` | Animation engine: discovers animations in `common/animations`, paces frames, and cycles them or runs them on a night schedule. |
| `night_schedule.py` | Computes sunset-to-sunrise windows (`NightSchedule`) used by the engine's `--night-schedule` mode. |

The agent controls RGB NeoPixel-compatible addressable strips. By default it runs in simulation so the command workflow can be tested before the LEDs are connected. From the repository root on the Pi, start the launcher:

```console
./pi_agent/agent_server.sh
```

The first run asks for the shared PC token and saves it under `~/.config/3dXmasTree`, outside the repository. The launcher creates/updates a virtual environment. When using a connected strip, start it with `--hardware`; the launcher installs the hardware dependencies as needed:

```console
./pi_agent/agent_server.sh --hardware
```

The agent loads GPIO pin, brightness, color order, test limit, and calibrated `led.led_count` from `common/settings.json`. Color and length setup tests use `led.test_count` (1000 by default) as their maximum address. Length setup lights one pixel; when the user presses **Done**, the Pi stores the preceding LED number as the calibrated length. Use a compatible power supply and common ground, and verify the GPIO wiring before enabling hardware mode.

The agent checks that it is running on the configured Pi hostname. Run it in an interactive SSH terminal. The command center stops it after **Yes** or **Abort**, and the Pi terminal logs the remote request and final shutdown. `Ctrl+Q` also stops it locally; `Ctrl+F4` works when the terminal forwards that key sequence.

## Animation Engine

`3dXmasTree.py` discovers concrete `Animation` subclasses recursively in `common/animations` and cycles through them. Each animation runs for 10 seconds by default at a 30 FPS target; it receives elapsed time through `doframe(dt)`. The engine owns frame pacing and strip output. Animations must not sleep in `doframe`.

General engine defaults live in `common/settings.json` under `animation`: `fps` and `seconds_per_animation`. Command-line `--fps` and `--seconds-per-animation` override them for a run.

The `3dXmasTree.sh` launcher creates or reuses `pi_agent/.venv`, scans `common/animations` for `requirements*.txt`, and installs the Pi hardware requirements only when `--hardware` is used:

```console
./pi_agent/3dXmasTree.sh
```

Useful options are `--list-animations`, `--once ANIMATION`, `--fps 60`, `--seconds-per-animation 5`, and `--hardware`. In hardware mode, calibrate and set `led.led_count` first. Without `-Hardware`, the engine uses the simulated strip and defaults to `led.capture_test_led_count`.

### Night Schedule

Continuous animation playback remains the default. Add `--night-schedule` to keep the LEDs off during the day and play random effects between adjusted sunset and sunrise. The Pi's configured local timezone is used for daylight-saving changes.

Set `night_schedule.latitude` and `night_schedule.longitude` in `common/settings.json` before enabling the schedule. `sunset_offset_minutes` and `sunrise_offset_minutes` shift those events; positive values delay them and negative values advance them. `opening_animation` and `closing_animation` are optional animation names. When set, they run once at the start and end of each night and are excluded from the random middle-of-night selection. Leave either blank to omit it.

`--once ANIMATION` plays only the named animation until `Ctrl+Q` (or `Ctrl+F4`) is pressed. It cannot be combined with `--night-schedule`.

Shared animations belong under `common/animations`. Put any third-party animation dependencies in a `requirements*.txt` file in that animation folder tree; the launcher discovers these recursively.