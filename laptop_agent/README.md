# Laptop camera agent

The laptop agent returns a JPEG snapshot from the configured webcam when the PC requests one.

```console
python -m pip install -r laptop_agent/requirements.txt
python laptop_agent/camera_server.py
```

Set the same `XMAS_AGENT_TOKEN` environment variable on all three computers before starting the agent. Configure the laptop hostname, port, camera device index, and JPEG quality in `common/settings.json`. The service listens on port `8766` by default.

The service checks that it is running on the configured laptop hostname. Run it in an interactive SSH terminal; `Ctrl+Q` stops it, and `Ctrl+F4` works when the terminal forwards that key sequence.