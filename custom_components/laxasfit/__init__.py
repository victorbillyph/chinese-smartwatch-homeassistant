"""LaxasFit BLE Watch integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import voluptuous as vol

from .ble_protocol import LaxasFitBLE
from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LaxasFit from a config entry."""
    address = entry.data["address"]
    ble = LaxasFitBLE(address)

    connected = await ble.connect(max_retries=6)
    if not connected:
        raise ConfigEntryNotReady(f"Could not connect to watch {address}")

    try:
        await ble.read_device_info()
    except Exception as err:
        _LOGGER.warning("Failed to read device info: %s", err)

    try:
        await ble.read_battery()
    except Exception as err:
        _LOGGER.warning("Failed to read battery: %s", err)

    try:
        await ble.bind()
    except Exception as err:
        _LOGGER.warning("Failed to bind: %s", err)

    try:
        await ble.sync_time()
    except Exception as err:
        _LOGGER.warning("Failed to sync time: %s", err)

    coordinator = LaxasFitCoordinator(hass, entry, ble)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "ble": ble,
        "coordinator": coordinator,
    }

    # Update config entry if fallback changed the address
    if ble.address.lower() != address.lower():
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "address": ble.address}
        )
        _LOGGER.info("Watch address updated: %s → %s", address, ble.address)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register notification service
    async def async_send_notification(call) -> None:
        message = call.data.get("message", "")
        title = call.data.get("title", "HA")
        msg_type = call.data.get("type", "other")

        data = hass.data[DOMAIN].get(entry.entry_id)
        if not data:
            return
        ble = data["ble"]
        if not ble.connected:
            _LOGGER.warning("Watch not connected, cannot send notification")
            return
        await ble.send_notification(msg_type, title, message)

    hass.services.async_register(
        DOMAIN,
        "send_notification",
        async_send_notification,
        schema=vol.Schema({
            vol.Required("message"): str,
            vol.Optional("title", default="HA"): str,
            vol.Optional("type", default="other"): str,
        }),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["ble"].disconnect()
    return unload_ok
