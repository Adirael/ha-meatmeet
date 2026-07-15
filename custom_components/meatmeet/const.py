"""Constants for the Meatmeet integration."""

from __future__ import annotations

import logging

DOMAIN = "meatmeet"
LOGGER = logging.getLogger(__package__)

# BLE identifiers (reverse-engineered from the Meatmeet S Pro).
CONTROL_SERVICE_UUID = "a6ed0401-d344-460a-8075-b9e8ec90d71b"
WRITE_CHAR_UUID = "a6ed0404-d344-460a-8075-b9e8ec90d71b"
NOTIFY_CHAR_UUID = "0000f5a1-0000-1000-8000-00805f9b34fb"

# 3-byte poll command written to the control characteristic to request a frame.
POLL_COMMAND = bytes([0x01, 0x06, 0x02])

# Config / options.
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 3  # seconds
