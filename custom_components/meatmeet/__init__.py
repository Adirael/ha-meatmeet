"""The Meatmeet Bluetooth thermometer integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
from .coordinator import MeatmeetCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
]

type MeatmeetConfigEntry = ConfigEntry[MeatmeetCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MeatmeetConfigEntry) -> bool:
    """Set up Meatmeet from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    if not bluetooth.async_ble_device_from_address(hass, address, connectable=True):
        raise ConfigEntryNotReady(
            f"Could not find Meatmeet {address}; waiting for it to come in range"
        )

    interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    coordinator = MeatmeetCoordinator(hass, entry, address, interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_shutdown)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeatmeetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: MeatmeetConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
