"""Config flow for the Meatmeet integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS

from .const import (
    CONF_POLL_INTERVAL,
    CONTROL_SERVICE_UUID,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)


def _is_meatmeet(info: BluetoothServiceInfoBleak) -> bool:
    """Return True if the advertisement looks like a Meatmeet station."""
    return CONTROL_SERVICE_UUID in info.service_uuids or (
        info.name or ""
    ).startswith("ME_BOX")


class MeatmeetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meatmeet."""

    def __init__(self) -> None:
        """Initialise the flow state."""
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a Meatmeet discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered device."""
        assert self._discovery is not None
        if user_input is not None:
            return self._create_entry(self._discovery.address, self._discovery.name)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery.name or self._discovery.address
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup by picking from discovered devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered.get(address)
            return self._create_entry(address, info.name if info else None)

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current_addresses or info.address in self._discovered:
                continue
            if _is_meatmeet(info):
                self._discovered[info.address] = info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: f"{info.name or 'Meatmeet'} ({address})"
            for address, info in self._discovered.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    def _create_entry(self, address: str, name: str | None) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=name or f"Meatmeet {address}",
            data={CONF_ADDRESS: address},
        )

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return MeatmeetOptionsFlow()


class MeatmeetOptionsFlow(OptionsFlow):
    """Handle Meatmeet options (poll interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL, default=current
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
                }
            ),
        )
