"""Binary sensor platform: per-zone "target reached".

On when the zone's live temperature has reached its target setpoint. Use it as
an automation trigger to get notified when a cook is done.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeatmeetConfigEntry
from .coordinator import MeatmeetCoordinator, meatmeet_device_info


async def async_setup_entry(
    hass,
    entry: MeatmeetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the per-zone target-reached binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeatmeetTargetReached(coordinator, zone) for zone in range(1, 6)
    )


class MeatmeetTargetReached(
    CoordinatorEntity[MeatmeetCoordinator], BinarySensorEntity
):
    """True once a zone's temperature reaches its target."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:thermometer-check"

    def __init__(self, coordinator: MeatmeetCoordinator, zone: int) -> None:
        """Initialise the binary sensor for a zone."""
        super().__init__(coordinator)
        self._zone = zone
        self._attr_name = f"Zone {zone} target reached"
        self._attr_unique_id = f"{coordinator.address}_zone{zone}_target_reached"
        self._attr_device_info = meatmeet_device_info(coordinator.address)

    def _current(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.zones[self._zone - 1]

    @property
    def available(self) -> bool:
        """Available only when a target is set and the probe is reading."""
        return (
            super().available
            and self.coordinator.targets.get(self._zone) is not None
            and self._current() is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if the current temperature has reached the target."""
        target = self.coordinator.targets.get(self._zone)
        current = self._current()
        if target is None or current is None:
            return None
        return current >= target
