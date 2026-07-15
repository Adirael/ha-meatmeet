"""Data update coordinator for the Meatmeet integration.

Maintains a persistent BLE connection to the Meatmeet S Pro station, subscribes
to notifications, and polls it once per update cycle by writing the poll command
to the control characteristic. Each poll triggers a 54-byte notification which is
parsed into a :class:`MeatmeetData`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import struct
from typing import TYPE_CHECKING

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    LOGGER,
    NOTIFY_CHAR_UUID,
    POLL_COMMAND,
    WRITE_CHAR_UUID,
)

if TYPE_CHECKING:
    from bleak.backends.characteristic import BleakGATTCharacteristic

    from . import MeatmeetConfigEntry

# 54-byte station frame layout.
PACKET_LEN = 54
HEADER = b"ME"  # 0x4D 0x45
TEMP_INVALID = 0xA000  # raw zone value at/above this = probe not connected


@dataclass
class MeatmeetData:
    """A single decoded reading from the station."""

    station_battery: int
    probe_battery: int
    ambient: float | None
    zones: list[float | None]  # Zone 1..5, index 0..4


def parse_packet(data: bytes) -> MeatmeetData | None:
    """Decode a 54-byte Meatmeet notification, or return None if not a frame."""
    if len(data) < PACKET_LEN or data[0:2] != HEADER:
        return None

    def zone(offset: int) -> float | None:
        raw = struct.unpack_from("<H", data, offset)[0]
        return None if raw >= TEMP_INVALID else raw / 100.0

    ambient_raw = data[13]
    return MeatmeetData(
        station_battery=data[8],
        probe_battery=data[15],
        ambient=float(ambient_raw) if 0 < ambient_raw < 250 else None,
        zones=[zone(11), zone(16), zone(18), zone(20), zone(22)],
    )


def meatmeet_device_info(address: str) -> DeviceInfo:
    """Device registry info shared by every Meatmeet entity."""
    return DeviceInfo(
        connections={(CONNECTION_BLUETOOTH, address)},
        name="Meatmeet S Pro",
        manufacturer="Meatmeet",
        model="S Pro",
    )


class MeatmeetCoordinator(DataUpdateCoordinator[MeatmeetData]):
    """Keeps a BLE connection to the station and refreshes readings on a timer."""

    config_entry: MeatmeetConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MeatmeetConfigEntry,
        address: str,
        interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Meatmeet {address}",
            update_interval=timedelta(seconds=interval),
        )
        self.address = address
        # Per-zone target temperatures (zone 1..5 -> °C), set from the number
        # entities and read by the "target reached" binary sensors. HA-side only;
        # the station's BLE protocol is read-only.
        self.targets: dict[int, float | None] = {zone: None for zone in range(1, 6)}
        self._client: BleakClientWithServiceCache | None = None
        self._latest: MeatmeetData | None = None
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()

    @callback
    def _handle_disconnect(self, _client: BleakClientWithServiceCache) -> None:
        LOGGER.debug("Meatmeet %s disconnected", self.address)

    @callback
    def _notification_handler(
        self, _char: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        parsed = parse_packet(bytes(data))
        if parsed is not None:
            self._latest = parsed
            self._event.set()

    async def _ensure_connected(self) -> None:
        if self._client is not None and self._client.is_connected:
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Meatmeet {self.address} not found — is it powered on, in range, "
                "and disconnected from the phone app?"
            )
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                disconnected_callback=self._handle_disconnect,
            )
            await client.start_notify(NOTIFY_CHAR_UUID, self._notification_handler)
        except (BleakError, TimeoutError) as err:
            raise UpdateFailed(
                f"Could not connect to Meatmeet {self.address}: {err}"
            ) from err
        self._client = client
        LOGGER.debug("Connected to Meatmeet %s", self.address)

    async def _async_update_data(self) -> MeatmeetData:
        async with self._lock:
            await self._ensure_connected()
            assert self._client is not None
            self._event.clear()
            try:
                await self._client.write_gatt_char(
                    WRITE_CHAR_UUID, POLL_COMMAND, response=False
                )
            except BleakError as err:
                await self._disconnect()
                raise UpdateFailed(
                    f"Failed to poll Meatmeet {self.address}: {err}"
                ) from err

            timeout = self.update_interval.total_seconds() + 5
            try:
                async with asyncio.timeout(timeout):
                    await self._event.wait()
            except TimeoutError:
                if self._latest is None:
                    raise UpdateFailed(
                        f"No data received from Meatmeet {self.address}"
                    ) from None
                LOGGER.debug(
                    "No fresh frame this cycle from %s; reusing last reading",
                    self.address,
                )
            return self._latest  # type: ignore[return-value]

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except BleakError as err:
                LOGGER.debug("Error disconnecting from %s: %s", self.address, err)

    async def async_shutdown(self) -> None:
        """Cancel the refresh timer and drop the BLE connection."""
        await super().async_shutdown()
        await self._disconnect()
