# Raspberry Pi LED agent

The agent controls RGB NeoPixel-compatible addressable strips. By default it runs in simulation so the command workflow can be tested before the LEDs are connected. From the repository root on the Pi, start the launcher:

```console
./pi_agent/run.sh
```

The first run asks for the shared PC token and saves it under `~/.config/3dXmasTree`, outside the repository. The launcher creates/updates a virtual environment. When using a connected strip, start it with `--hardware`; the launcher installs the hardware dependencies as needed:

```console
./pi_agent/run.sh --hardware
```

The agent loads GPIO pin, brightness, color order, test limit, and calibrated `led.led_count` from `common/settings.json`. Color and length setup tests use `led.test_count` (1000 by default) as their maximum address. Length setup lights one pixel; when the user presses **Done**, the Pi stores the preceding LED number as the calibrated length. Use a compatible power supply and common ground, and verify the GPIO wiring before enabling hardware mode.

The agent checks that it is running on the configured Pi hostname. Run it in an interactive SSH terminal. The command center stops it after **Yes** or **Abort**, and the Pi terminal logs the remote request and final shutdown. `Ctrl+Q` also stops it locally; `Ctrl+F4` works when the terminal forwards that key sequence.

## Animation Engine

`3dXmasTree.py` discovers concrete `Animation` subclasses recursively in `common/animations` and cycles through them. Each animation runs for 10 seconds by default at a 30 FPS target; it receives elapsed time through `doframe(dt)`. The engine owns frame pacing and strip output. Animations must not sleep in `doframe`.

General engine defaults live in `common/settings.json` under `animation`: `fps` and `seconds_per_animation`. Command-line `--fps` and `--seconds-per-animation` override them for a run.

The PowerShell Core launcher creates or reuses `pi_agent/.venv`, scans `common/animations` for `requirements*.txt`, and installs the Pi hardware requirements only when `-Hardware` is used. PowerShell Core (`pwsh`) must be installed on the Pi to use this wrapper:

```powershell
pwsh -File ./pi_agent/3dXmasTree.ps1
```

Useful options are `-ListAnimations`, `-Once`, `-Fps 60`, `-SecondsPerAnimation 5`, and `-Hardware`. In hardware mode, calibrate and set `led.led_count` first. Without `-Hardware`, the engine uses the simulated strip and defaults to `led.capture_test_led_count`.

Shared animations belong under `common/animations`. Put any third-party animation dependencies in a `requirements*.txt` file in that animation folder tree; the launcher discovers these recursively.