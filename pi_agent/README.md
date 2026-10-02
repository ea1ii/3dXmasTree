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