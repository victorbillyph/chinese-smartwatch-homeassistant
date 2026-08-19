"""Notify entity for LaxasFit BLE Watch."""
from __future__ import annotations

import logging

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([LaxasFitNotifyEntity(entry)])


class LaxasFitNotifyEntity(NotifyEntity):
    """Send notifications to the LaxasFit watch screen."""

    _attr_has_entity_name = True
    _attr_name = "Watch Notifications"
    _attr_icon = "mdi:bell"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610",
        }

    @property
    def ble(self):
        return self.hass.data[DOMAIN][self._entry.entry_id]["ble"]

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        if not self.ble.connected:
            _LOGGER.warning("Watch not connected, cannot send notification")
            return

        msg_type = "other"
        if title:
            lower = title.lower()
            if "whatsapp" in lower:
                msg_type = "whatsapp"
            elif "telegram" in lower:
                msg_type = "telegram"
            elif "instagram" in lower:
                msg_type = "instagram"
            elif "facebook" in lower:
                msg_type = "facebook"
            elif "twitter" in lower:
                msg_type = "twitter"
            elif "sms" in lower:
                msg_type = "sms"

        await self.ble.send_notification(msg_type, title or "HA", message)
