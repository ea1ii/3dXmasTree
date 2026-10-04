# 3dXmasTree
A 3D Xmas tree LED strip

## Agent Layout

- `pc_agent` is the command center and owns the operator UI.
- `pi_agent` runs the LED command service and animation engine; shared animation classes live in `common/animations/`.
- `laptop_agent` runs the webcam service and returns JPEG snapshots on request.
- `common/settings.json` contains LAN hostnames, ports, LED test limit and calibrated LED count, GPIO pin, and camera settings. Keep the file in sync on each computer.

The agents communicate over HTTP on the trusted local network. The launchers load `XMAS_AGENT_TOKEN` from a local token file outside the repository. Do not commit or share the token. Allow the PC to reach the Pi on port `8765` and the laptop on port `8766` through the local firewall. The HTTP traffic is not encrypted, so do not expose these ports to an untrusted network.

Every runnable entry point checks its configured host in `common/Xmas_shared.py` and exits if launched on the wrong machine. Update the hostname constants there if a device hostname changes. The PC command center closes with `Ctrl+F4` or `Ctrl+Q`.

## Run The Setup Workflows

Pull the latest repository on all three computers first, so they have matching settings and port configuration. The launch scripts create a per-agent virtual environment, install requirements when they change, and activate the environment for that process. You no longer need to activate a venv or set `XMAS_AGENT_TOKEN` manually.

### 1. Start The PC Command Center

In PowerShell, from the repository root:

```console
.\pc_agent\run.ps1
```

On first run, the launcher creates a random token, saves it under your Windows local application data (outside the repository), and prints it once. Keep it private. The command center then starts using its own `.venv`.

If PowerShell blocks the script, run it without changing the machine's execution policy:

```console
powershell -ExecutionPolicy Bypass -File .\pc_agent\run.ps1
```

### 2. Start The Laptop Camera Agent

In PowerShell, from the repository root on the laptop:

```console
.\laptop_agent\run.ps1
```

The launcher creates its own `.venv` and installs OpenCV. The first run asks for the token printed by the PC launcher using a hidden prompt, then saves it under Windows local application data. Later runs reuse it automatically. If PowerShell blocks the script, use:

```console
powershell -ExecutionPolicy Bypass -File .\laptop_agent\run.ps1
```

### 3. Start The Pi LED Agent

In the Pi's SSH terminal, from the repository root:

```console
./pi_agent/agent_server.sh
```

The first run asks for the same PC token using a hidden prompt and saves it under `~/.config/3dXmasTree`, outside the repository. By default, the Pi runs in simulation mode. Hardware dependencies are installed only when requested:

```console
./pi_agent/agent_server.sh --hardware
```

Do not use `--hardware` until the strip, power supply, LED count, pin, and color order are verified.

Each launcher reuses its local token on later runs. If you need to rotate the shared token, delete the local token file on each computer and restart the PC launcher first to create a new one; enter that new token in the laptop and Pi prompts. Never commit these local token files.

Run both agents in their foreground terminals. On **Yes** or **Abort**, the command center sends authenticated shutdown requests to both agents. Each remote terminal logs that shutdown was requested and then confirms when its agent stops; the SSH sessions themselves remain open for you to close. If shutdown cannot reach an agent, the command center identifies it so you can stop it manually. You can also stop agents locally with `Ctrl+Q`; `Ctrl+F4` is recognized only if the SSH terminal forwards it.

Choose **Setup Color** to step through all six RGB channel orders. The default test count is 1000 and the expected test color is `#FF8040`. **Yes** stores the selected order in `common/settings.json` on both the PC and Pi; **No** advances; **Abort** turns the strip off without saving.

Choose **Setup LED Length** to light one LED at a time while the laptop image refreshes. **Next** advances to the next LED; **Previous** returns to the prior LED and is disabled at LED 1. When the displayed LED does not light, **Done** treats it as beyond the strip and saves the previous number as `led.led_count` on both PC and Pi. **Abort** cancels without changing the saved count. `led.test_count` (1000 by default) is the maximum address the test will try; increase it if the strip is longer.

Choose **Calibrate** and select a timestamped folder under `pc_agent/frames/`. Calibration detects the brightest spot in each image, matches Front/Back and Left/Right detections within the adjustable tolerance, builds 3D points, and adjusts consecutive points that exceed `led.maxLEDdist`. The initial cone height/width is estimated from the detections and stays centered at `(0, 0, 0)`. The lowest detected LED defines the point origin; height/width controls change only the cone, while the six directional controls offset only the LED coordinates. **Back to Interpolation** clears the LED offset while keeping the chosen cone size. Cyan XY/XZ/YZ references remain fixed at the origin, and the fitted cone is outlined in green in flat views. Enable **Adjust LED Centers** in Picture mode to show red crosshairs; drag a crosshair and release to recalculate that LED's position. The four flat views can independently show their source picture or the geometric model; the shared controls navigate frames and switch all views. Review point status and coordinates in the table and 3D model, then save `positions_<source timestamp>.json` beside the source frames. The file records LED index and X/Y/Z coordinates in millimeters, along with the cone dimensions and LED offset.

`led.maxLEDdist` is a physical distance in millimeters (currently `120`). Camera images remain measured in pixels; this setting does not change image dimensions.

`camera.frame_height_mm` is currently assumed to be `1500`, the physical vertical span covered by a captured frame. Pixel-to-millimeter conversion is not applied yet.

Choose **Grab Positions** to capture the configured test LEDs from **Front**, **Right**, **Left**, and **Back**. Before each sweep, rotate the tree as instructed and confirm to continue. The PC saves one JPEG per LED as `<view>_LED_<number>.jpg` in `pc_agent/frames/<yyyymmdd_hhmm>/`; LED numbers are zero-padded to three digits. The default test is 100 LEDs per view (400 images total). `led.capture_test_led_count` controls this test count. **Abort** stops capture and both agent scripts; images already captured remain in the session folder. The `pc_agent/frames/` directory is tracked, but generated session folders and images are ignored by Git.

For simulated position captures, LED 1 starts at the tree-base center. The remaining LEDs follow a randomized 3D walk through the interior of a conical tree model, using shuffled height bands rather than a regular spiral. Adjacent LEDs are spaced no farther apart than `led.maxLEDdist` (120 mm); the assumed simulated tree height is `led.simulated_tree_height_mm` (1200 mm). The camera frame's vertical coverage is `camera.frame_height_mm` (1500 mm). The image is kept in pixel dimensions; these assumptions are used only to project each 3D LED location into the frame. With `camera.simulate_led_lights` enabled, the frame background is darkened to `camera.synthetic_background_level` and an irregular, bright-centered glow is added at the projected LED pixel before display and saving.

When synthetic lights are enabled, the capture page also shows that same 3D tree as a translucent model, with solid LED markers and links between consecutive LEDs; the currently lit LED is highlighted before its image is captured.

Before using the Pi's physical strip, set its correct host, test limit, pin, brightness, color order, and camera host in `common/settings.json`. Run **Setup LED Length** to measure and store `led.led_count`; `led.test_count` is only the scan limit. Start the Pi with `./pi_agent/agent_server.sh --hardware`. The current code assumes a three-channel NeoPixel-compatible strip.

## Acknowledgements

Credit to [Matt Parker](https://github.com/standupmaths) of [Stand-up Maths](https://www.youtube.com/@standupmaths) for the inspiration.

When I saw his 3D Xmas Tree video in YouTube I told myself 'I need to do that!' Some LED strip has been hunging from my curtain bar ever since doing nothing but gathering dust and cowebs.

Then AI came into play. I was initially reluctant but... was dragged into it like a moth to a flame.

Result? 10,000+ lines of code, from which, in all honesty, not many were written by myself.

If you like the project. Feel free to collaborate.

It's weird to say this with October just started, but Happy Xmas, all!

