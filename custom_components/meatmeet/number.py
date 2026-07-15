"""Number platform: per-zone target temperature setpoints.

These are Home Assistant-side targets (the station's BLE protocol is read-only).
The matching "target reached" binary sensors compare them against live readings.
"""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MeatmeetConfigEntry
from .coordinator import MeatmeetCoordinator, meatmeet_device_info


async def async_setup_entry(
    hass,
    entry: MeatmeetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the per-zone target temperature numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeatmeetTargetNumber(coordinator, zone) for zone in range(1, 6)
    )


class MeatmeetTargetNumber(RestoreNumber):
    """A user-settable target temperature for one zone, restored on restart."""

    _attr_has_entity_name = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: MeatmeetCoordinator, zone: int) -> None:
        """Initialise the target number for a zone."""
        self._coordinator = coordinator
        self._zone = zone
        self._attr_name = f"Zone {zone} target"
        self._attr_unique_id = f"{coordinator.address}_zone{zone}_target"
        self._attr_device_info = meatmeet_device_info(coordinator.address)
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Restore the last target and publish it to the coordinator."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        self._coordinator.targets[self._zone] = self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set a new target temperature."""
        self._attr_native_value = value
        self._coordinator.targets[self._zone] = value
        self.async_write_ha_state()
        # Push so the "target reached" binary sensor re-evaluates immediately.
        self._coordinator.async_update_listeners()
