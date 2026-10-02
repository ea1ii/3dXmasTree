# Xmas_shared.py
# Shared functions and configuration constants for 3dXmasTree.
#
# Copyright (c) 2026 Carlos Gil
# Licensed under the MIT License. See LICENSE for details.

import os
import select
import socket
import sys
import threading
import time

LAPTOP_HOSTNAME = "CG-laptop"
PC_HOSTNAME = "CGmainComputer"
PI_HOSTNAME = "CGlab"

__all__ = [
	"LAPTOP_HOSTNAME",
	"PC_HOSTNAME",
	"PI_HOSTNAME",
	"isLaptop",
	"isPC",
	"isPi",
	"require_platform",
	"start_exit_key_monitor",
]


def _detect_platform():
	"""Return the configured platform name, or None if the host is unknown."""
	hostname = socket.gethostname().strip().lower()
	platform_hostnames = {
		"laptop": LAPTOP_HOSTNAME,
		"pc": PC_HOSTNAME,
		"pi": PI_HOSTNAME,
	}
	for platform_name, configured_hostname in platform_hostnames.items():
		if configured_hostname.strip().lower() == hostname:
			return platform_name
	return None


def isLaptop():
	return _detect_platform() == "laptop"


def isPC():
	return _detect_platform() == "pc"


def isPi():
	return _detect_platform() == "pi"


def require_platform(expected_platform):
	platform_names = {
		"laptop": LAPTOP_HOSTNAME,
		"pc": PC_HOSTNAME,
		"pi": PI_HOSTNAME,
	}
	if expected_platform not in platform_names:
		raise ValueError(f"Unknown platform: {expected_platform}")

	actual_platform = _detect_platform()
	if actual_platform != expected_platform:
		expected_host = platform_names[expected_platform]
		actual_host = socket.gethostname()
		raise SystemExit(
			f"This script must run on the {expected_platform} "
			f"({expected_host}); current host is {actual_host}."
		)


def _is_ctrl_f4(sequence):
	return (
		sequence in (b"\x1b[1;5S", b"\x1b[5;5~")
		or (
			sequence.startswith(b"\x1b[")
			and sequence.endswith(b"S")
			and b";5" in sequence
		)
	)


def _watch_posix_exit_keys(on_exit, stop_event):
	import termios

	file_descriptor = sys.stdin.fileno()
	original_settings = termios.tcgetattr(file_descriptor)
	terminal_settings = termios.tcgetattr(file_descriptor)
	terminal_settings[0] &= ~termios.IXON
	terminal_settings[3] &= ~(termios.ICANON | termios.ECHO)
	terminal_settings[6] = terminal_settings[6][:]
	terminal_settings[6][termios.VMIN] = 0
	terminal_settings[6][termios.VTIME] = 0
	termios.tcsetattr(file_descriptor, termios.TCSANOW, terminal_settings)

	try:
		while not stop_event.is_set():
			readable, _, _ = select.select([file_descriptor], [], [], 0.1)
			if not readable:
				continue

			key = os.read(file_descriptor, 1)
			if key == b"\x11":
				break
			if key != b"\x1b":
				continue

			sequence = bytearray(key)
			deadline = time.monotonic() + 0.2
			while len(sequence) < 16 and time.monotonic() < deadline:
				readable, _, _ = select.select([file_descriptor], [], [], 0.02)
				if not readable:
					break
				sequence.extend(os.read(file_descriptor, 1))
				if sequence[-1:] in (b"S", b"~"):
					break
			if _is_ctrl_f4(bytes(sequence)):
				break
	finally:
		termios.tcsetattr(file_descriptor, termios.TCSANOW, original_settings)

	if stop_event.is_set():
		return
	print("Exit shortcut received; stopping agent.")
	on_exit()


def _watch_windows_exit_keys(on_exit, stop_event):
	import ctypes
	import msvcrt

	while not stop_event.is_set():
		key = msvcrt.getwch()
		if key == "\x11":
			break
		if key not in ("\x00", "\xe0"):
			continue
		msvcrt.getwch()
		control_down = ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000
		f4_down = ctypes.windll.user32.GetAsyncKeyState(0x73) & 0x8000
		if control_down and f4_down:
			break

	if not stop_event.is_set():
		print("Exit shortcut received; stopping agent.")
		on_exit()


class ExitKeyMonitor:
	def __init__(self, on_exit):
		self.stop_event = threading.Event()
		watcher = _watch_windows_exit_keys if os.name == "nt" else _watch_posix_exit_keys
		self.thread = threading.Thread(
			target=watcher,
			args=(on_exit, self.stop_event),
			daemon=True,
		)
		self.thread.start()

	def stop(self):
		self.stop_event.set()
		self.thread.join(timeout=0.5)


def start_exit_key_monitor(on_exit):
	if not sys.stdin.isatty():
		return None

	return ExitKeyMonitor(on_exit)
