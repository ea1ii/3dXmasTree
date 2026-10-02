# Xmas_shared.py
# Shared functions and configuration constants for 3dXmasTree.
#
# Copyright (c) 2026 Carlos Gil
# Licensed under the MIT License. See LICENSE for details.

import socket

LAPTOP_HOSTNAME = "todo"
PC_HOSTNAME = "CGmainComputer"
PI_HOSTNAME = "CGlab"

__all__ = [
	"LAPTOP_HOSTNAME",
	"PC_HOSTNAME",
	"PI_HOSTNAME",
	"isLaptop",
	"isPC",
	"isPi",
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
