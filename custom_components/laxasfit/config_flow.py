"""Config flow for LaxasFit BLE Watch."""
from __future__ import annotations

import logging
from typing import Any

from bleak import BleakScanner
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address"): str,
        vol.Optional("name", default="Watch"): str,
    }
)


async def _async_get_devices(hass: HomeAssistant) -> dict[str, str]:
    """Scan for BLE devices and return name -> address mapping."""
    devices = await BleakScanner.discover(timeout=10)
    return {
        f"{d.name or 'Unknown'} [{d.address}]": d.address
        for d in devices
        if d.name and any(
            n in d.name.lower()
            for n in ("watch", "laxasfit", "hryfine")
        )
    }


class LaxasFitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LaxasFit BLE Watch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input["address"]
            await self.async_set_unique_id(address.lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get("name", "Watch"),
                data={
                    "address": address,
                    "name": user_input.get("name", "Watch"),
                },
            )

        # Try to discover devices
        try:
            devices = await _async_get_devices(self.hass)
        except Exception:
            devices = {}

        if devices:
            schema = vol.Schema(
                {
                    vol.Required("address"): vol.In(devices),
                    vol.Optional("name", default="Watch"): str,
                }
            )
        else:
            schema = STEP_USER_DATA_SCHEMA

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
