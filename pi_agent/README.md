# Raspberry Pi LED agent

The agent controls RGB NeoPixel-compatible addressable strips. By default it runs in simulation so the command workflow can be tested before the LEDs are connected. Start the network service from the project root:

```console
python pi_agent/agent_server.py
```

Install hardware dependencies before using a connected strip:

```console
python -m pip install -r pi_agent/requirements.txt
python pi_agent/agent_server.py --hardware
```

The agent loads the LED count, GPIO pin, brightness, and selected pixel order from `common/settings.json`. The initial color setup uses the configurable `led.test_count` (1000 by default) to write past the physical strip length so every connected pixel receives data. Use a compatible power supply and common ground, and verify the GPIO wiring before enabling hardware mode.

The agent checks that it is running on the configured Pi hostname. Run it in an interactive SSH terminal; `Ctrl+Q` stops it, and `Ctrl+F4` works when the terminal forwards that key sequence.