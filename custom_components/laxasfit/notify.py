"""Notification platform for LaxasFit BLE Watch.

Send notifications directly to the watch screen via HA notification service.
"""
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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None,
    discovery_info: None = None,
) -> LaxasFitNotificationService | None:
    if config_entry is None:
        return None
    return LaxasFitNotificationService(hass, config_entry)


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
