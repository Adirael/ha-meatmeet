"""Binary sensor platform: per-zone "target reached".

On when the zone's live temperature has reached its target setpoint. Use it as
an automation trigger to get notified when a cook is done.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeatmeetConfigEntry
from .coordinator import MeatmeetCoordinator, meatmeet_device_info


async def async_setup_entry(
    hass,
    entry: MeatmeetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the target-reached and connectivity binary sensors."""
    coordinator = entry.runtime_data
    entities: list[CoordinatorEntity] = [
        MeatmeetTargetReached(coordinator, zone) for zone in range(1, 6)
    ]
    entities.append(MeatmeetConnected(coordinator))
    entities.append(MeatmeetOnStation(coordinator))
    async_add_entities(entities)


class MeatmeetOnStation(
    CoordinatorEntity[MeatmeetCoordinator], BinarySensorEntity
):
    """True while the probe is seated on the charging station."""

    _attr_has_entity_name = True
    _attr_name = "On station"
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator: MeatmeetCoordinator) -> None:
        """Initialise the dock sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_on_station"
        self._attr_device_info = meatmeet_device_info(coordinator.address)

    @property
    def available(self) -> bool:
        """Available when the coordinator has a reading."""
        return super().available and self.coordinator.data is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if the probe is docked on the station."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.docked


class MeatmeetConnected(
    CoordinatorEntity[MeatmeetCoordinator], BinarySensorEntity
):
    """Diagnostic: whether Home Assistant holds a live BLE connection."""

    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MeatmeetCoordinator) -> None:
        """Initialise the connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_connected"
        self._attr_device_info = meatmeet_device_info(coordinator.address)

    @property
    def available(self) -> bool:
        """Always available so it can report the disconnected state itself."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True while connected."""
        return self.coordinator.is_connected


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
