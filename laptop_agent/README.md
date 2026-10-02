# Laptop camera agent

The laptop agent returns a JPEG snapshot from the configured webcam when the PC requests one.

From PowerShell at the repository root, run:

```powershell
.\laptop_agent\run.ps1
```

The launcher creates/updates its virtual environment and asks for the shared PC token on first run. It saves the token under Windows local application data, outside the repository. Configure the laptop hostname, port, camera device index, and JPEG quality in `common/settings.json`. The service listens on port `8766` by default.

The service checks that it is running on the configured laptop hostname. Run it in an interactive SSH terminal; `Ctrl+Q` stops it, and `Ctrl+F4` works when the terminal forwards that key sequence.