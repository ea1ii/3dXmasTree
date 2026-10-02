# Raspberry Pi LED agent

The agent controls RGB NeoPixel-compatible addressable strips. By default it runs in simulation so the command workflow can be tested before the LEDs are connected. From the repository root on the Pi, start the launcher:

```console
./pi_agent/run.sh
```

The first run asks for the shared PC token and saves it under `~/.config/3dXmasTree`, outside the repository. The launcher creates/updates a virtual environment. When using a connected strip, start it with `--hardware`; the launcher installs the hardware dependencies as needed:

```console
./pi_agent/run.sh --hardware
```

The agent loads the LED count, GPIO pin, brightness, and selected pixel order from `common/settings.json`. The initial color setup uses the configurable `led.test_count` (1000 by default) to write past the physical strip length so every connected pixel receives data. Use a compatible power supply and common ground, and verify the GPIO wiring before enabling hardware mode.

The agent checks that it is running on the configured Pi hostname. Run it in an interactive SSH terminal; `Ctrl+Q` stops it, and `Ctrl+F4` works when the terminal forwards that key sequence.