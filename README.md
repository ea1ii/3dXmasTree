# 3dXmasTree
A 3D Xmas tree LED strip

## Agent Layout

- `pc_agent` is the command center and owns the operator UI.
- `pi_agent` runs the LED command service. It simulates the strip by default; use `--hardware` only when the strip is connected and configured.
- `laptop_agent` runs the webcam service and returns JPEG snapshots on request.
- `common/settings.json` contains LAN hostnames, ports, LED test count, GPIO pin, and camera settings. Keep the file in sync on each computer.

The agents communicate over HTTP on the trusted local network. Set the same private `XMAS_AGENT_TOKEN` environment variable on the PC, Pi, and laptop before starting their agents. Do not commit or share the token. Allow the PC to reach the Pi on port `8765` and the laptop on port `8766` through the local firewall. The HTTP traffic is not encrypted, so do not expose these ports to an untrusted network.

Every runnable entry point checks its configured host in `common/Xmas_shared.py` and exits if launched on the wrong machine. Update the hostname constants there if a device hostname changes. The PC command center closes with `Ctrl+F4` or `Ctrl+Q`.

## Run The Color Setup

On the Pi, install `pi_agent/requirements.txt`, set `XMAS_AGENT_TOKEN`, then start the simulated agent:

```console
python pi_agent/agent_server.py
```

On the laptop, install `laptop_agent/requirements.txt`, set the same token, then start the camera agent:

```console
python laptop_agent/camera_server.py
```

On the PC, set the token, install the root `requirements.txt`, then start the command center:

```console
python -m pip install -r requirements.txt
python pc_agent/main.py
```

Choose **Setup Color** to step through all six RGB channel orders. The default test count is 1000 and the expected test color is `#FF8040`. **Yes** stores the selected order in `common/settings.json` on both the PC and Pi; **No** advances; **Abort** turns the strip off without saving.

Run the Pi and laptop agents in their foreground SSH terminals. Press `Ctrl+Q` to stop either agent; `Ctrl+F4` is also recognized if the SSH terminal forwards that key sequence instead of consuming it. Keep the remote terminal interactive. When color setup ends, the command center reminds the user to stop both agents and close their SSH sessions.

Before using the Pi's physical strip, set its correct host, LED count, pin, brightness, and camera host in `common/settings.json`. Then start the Pi service with `python pi_agent/agent_server.py --hardware`. The current code assumes a three-channel NeoPixel-compatible strip.
