"""Sensor platform for the Meatmeet integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MeatmeetConfigEntry
from .coordinator import MeatmeetCoordinator, MeatmeetData, meatmeet_device_info


@dataclass(frozen=True, kw_only=True)
class MeatmeetSensorDescription(SensorEntityDescription):
    """Describes a Meatmeet sensor."""

    value_fn: Callable[[MeatmeetData], float | int | None]


SENSORS: tuple[MeatmeetSensorDescription, ...] = (
    *(
        MeatmeetSensorDescription(
            key=f"zone{i}",
            name=f"Zone {i}",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=lambda d, i=i: d.zones[i - 1],
        )
        for i in range(1, 6)
    ),
    MeatmeetSensorDescription(
        key="ambient",
        name="Ambient",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.ambient,
    ),
    MeatmeetSensorDescription(
        key="station_battery",
        name="Station battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.station_battery,
    ),
    MeatmeetSensorDescription(
        key="probe_battery",
        name="Probe battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.probe_battery,
    ),
)


async def async_setup_entry(
    hass,
    entry: MeatmeetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meatmeet sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        MeatmeetSensor(coordinator, description) for description in SENSORS
    )


class MeatmeetSensor(CoordinatorEntity[MeatmeetCoordinator], SensorEntity):
    """A single Meatmeet reading exposed as a sensor."""

    entity_description: MeatmeetSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeatmeetCoordinator,
        description: MeatmeetSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = meatmeet_device_info(coordinator.address)

    @property
    def native_value(self) -> float | int | None:
        """Return the current value for this sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data and last update succeeded."""
        return super().available and self.coordinator.data is not None
