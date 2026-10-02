# 3dXmasTree
A 3D Xmas tree LED strip

## Agent Layout

- `pc_agent` is the command center and owns the operator UI.
- `pi_agent` runs the LED command service. It simulates the strip by default; use `--hardware` only when the strip is connected and configured.
- `laptop_agent` runs the webcam service and returns JPEG snapshots on request.
- `common/settings.json` contains LAN hostnames, ports, LED test count, GPIO pin, and camera settings. Keep the file in sync on each computer.

The agents communicate over HTTP on the trusted local network. The launchers load `XMAS_AGENT_TOKEN` from a local token file outside the repository. Do not commit or share the token. Allow the PC to reach the Pi on port `8765` and the laptop on port `8766` through the local firewall. The HTTP traffic is not encrypted, so do not expose these ports to an untrusted network.

Every runnable entry point checks its configured host in `common/Xmas_shared.py` and exits if launched on the wrong machine. Update the hostname constants there if a device hostname changes. The PC command center closes with `Ctrl+F4` or `Ctrl+Q`.

## Run The Color Setup

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
./pi_agent/run.sh
```

The first run asks for the same PC token using a hidden prompt and saves it under `~/.config/3dXmasTree`, outside the repository. By default, the Pi runs in simulation mode. Hardware dependencies are installed only when requested:

```console
./pi_agent/run.sh --hardware
```

Do not use `--hardware` until the strip, power supply, LED count, pin, and color order are verified.

Each launcher reuses its local token on later runs. If you need to rotate the shared token, delete the local token file on each computer and restart the PC launcher first to create a new one; enter that new token in the laptop and Pi prompts. Never commit these local token files.

Run both agents in their foreground terminals. Press `Ctrl+Q` to stop either agent; `Ctrl+F4` is recognized only if the SSH terminal forwards it. When color setup ends, the command center reminds you to stop both remote agents and close their SSH sessions.

Choose **Setup Color** to step through all six RGB channel orders. The default test count is 1000 and the expected test color is `#FF8040`. **Yes** stores the selected order in `common/settings.json` on both the PC and Pi; **No** advances; **Abort** turns the strip off without saving.

Before using the Pi's physical strip, set its correct host, LED count, pin, brightness, and camera host in `common/settings.json`. Start the Pi with `./pi_agent/run.sh --hardware`. The current code assumes a three-channel NeoPixel-compatible strip.
