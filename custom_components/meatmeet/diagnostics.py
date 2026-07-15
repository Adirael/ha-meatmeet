"""Diagnostics support for the Meatmeet integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import MeatmeetConfigEntry

TO_REDACT = {CONF_ADDRESS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeatmeetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    info = async_last_service_info(hass, coordinator.address, connectable=True)

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "connection": {
            "connected": coordinator.is_connected,
            "last_update_success": coordinator.last_update_success,
            "last_frame_time": (
                coordinator.last_frame_time.isoformat()
                if coordinator.last_frame_time
                else None
            ),
            "poll_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "rssi": info.rssi if info else None,
            "advertisement_seen": info is not None,
        },
        "targets": coordinator.targets,
        "data": asdict(coordinator.data) if coordinator.data else None,
    }
