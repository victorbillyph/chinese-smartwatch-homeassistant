"""Notification platform for LaxasFit BLE Watch."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LaxasFit notify platform."""
    # Notify is a service, not an entity platform.
    # We register the service here.
    async def async_send_to_watch(call):
        """Handle the send_to_watch service call."""
        message = call.data.get("message", "")
        title = call.data.get("title", "HA")
        msg_type = call.data.get("type", "other")

        data = hass.data[DOMAIN].get(entry.entry_id)
        if not data:
            _LOGGER.warning("Watch not configured")
            return

        ble = data["ble"]
        if not ble.connected:
            _LOGGER.warning("Watch not connected")
            return

        await ble.send_notification(msg_type, title, message)

    hass.services.async_register(
        DOMAIN,
        "send_notification",
        async_send_to_watch,
        schema=None,
    )


class LaxasFitNotificationService(BaseNotificationService):
    """Send notifications to the LaxasFit watch."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__()
        self._entry = entry
        self._hass = hass

    @property
    def ble(self):
        return self._hass.data[DOMAIN][self._entry.entry_id]["ble"]

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        title = kwargs.get(ATTR_TITLE, "HA")
        msg_type = kwargs.get("type", "other")

        if not self.ble.connected:
            _LOGGER.warning("Watch not connected, cannot send notification")
            return

        await self.ble.send_notification(msg_type, title, message)
