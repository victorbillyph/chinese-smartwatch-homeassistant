"""Button entities for LaxasFit BLE Watch."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LaxasFitButtonEntityDescription(ButtonEntityDescription):
    press_fn: Callable[..., Coroutine[Any, Any, Any]]


async def _find_watch(ble) -> None:
    await ble.find_watch()


async def _sync_time(ble) -> None:
    await ble.sync_time()


async def _request_all_data(ble) -> None:
    await ble.request_sport_data(1)


async def _music_play(ble) -> None:
    await ble.music_control("play")


async def _music_pause(ble) -> None:
    await ble.music_control("pause")


async def _music_next(ble) -> None:
    await ble.music_control("next")


async def _music_prev(ble) -> None:
    await ble.music_control("prev")


async def _reconnect(ble) -> None:
    if not ble.connected:
        await ble.connect(max_retries=3)


BUTTON_DESCRIPTIONS: tuple[LaxasFitButtonEntityDescription, ...] = (
    LaxasFitButtonEntityDescription(
        key="find_watch",
        name="Find Watch",
        icon="mdi:vibrate",
        press_fn=lambda ble: _find_watch(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="sync_time",
        name="Sync Time",
        icon="mdi:clock-check",
        press_fn=lambda ble: _sync_time(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="sync_data",
        name="Sync Data",
        icon="mdi:refresh",
        press_fn=lambda ble: _request_all_data(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="music_play",
        name="Play",
        icon="mdi:play",
        press_fn=lambda ble: _music_play(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="music_pause",
        name="Pause",
        icon="mdi:pause",
        press_fn=lambda ble: _music_pause(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="music_next",
        name="Next Track",
        icon="mdi:skip-next",
        press_fn=lambda ble: _music_next(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="music_prev",
        name="Previous Track",
        icon="mdi:skip-previous",
        press_fn=lambda ble: _music_prev(ble),
    ),
    LaxasFitButtonEntityDescription(
        key="reconnect",
        name="Reconnect",
        icon="mdi:bluetooth-connect",
        press_fn=lambda ble: _reconnect(ble),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [LaxasFitButton(coordinator, entry, d) for d in BUTTON_DESCRIPTIONS]
    entities.append(LaxasFitVoiceTriggerButton(coordinator, entry))
    entities.append(LaxasFitAnnounceButton(coordinator, entry))
    async_add_entities(entities)


class LaxasFitButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    entity_description: LaxasFitButtonEntityDescription

    def __init__(
        self,
        coordinator: LaxasFitCoordinator,
        entry: ConfigEntry,
        description: LaxasFitButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610",
        }

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.ble)


class LaxasFitVoiceTriggerButton(CoordinatorEntity, ButtonEntity):
    """Triggers HA voice assistant pipeline when pressed.

    Repurposes the watch's button as a voice assistant trigger.
    Works with HA's conversation agent or wake word detection.
    """

    _attr_has_entity_name = True
    _attr_name = "Voice Assistant Trigger"
    _attr_icon = "mdi:microphone"

    def __init__(self, coordinator: LaxasFitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_voice_trigger"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610 (HFP Mic)",
        }

    async def async_press(self) -> None:
        """Trigger voice assistant from watch microphone (BT Classic HFP)."""
        _LOGGER.info("Voice assistant triggered from watch")
        self.coordinator.ble.state.voice_assistant_active = True
        self.async_write_ha_state()

        # Try HA conversation agent
        try:
            await self.hass.services.async_call(
                "conversation", "process",
                {"agent_id": "conversation.home_assistant", "text": ""},
                blocking=False,
            )
        except Exception as err:
            _LOGGER.debug("Conversation agent not available: %s", err)

        # Try wake word detection
        try:
            await self.hass.services.async_call(
                "wake_word", "detect",
                {"entity_id": "wake_word.laxasfit_watch"},
                blocking=False,
            )
        except Exception:
            pass

        await asyncio.sleep(30)
        self.coordinator.ble.state.voice_assistant_active = False
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "bt_classic_address": self.coordinator.ble.state.bt_classic_address,
            "hfp_connected": self.coordinator.ble.state.bt_hfp_connected,
        }


class LaxasFitAnnounceButton(CoordinatorEntity, ButtonEntity):
    """Announce a TTS message through the watch BT speaker (A2DP)."""

    _attr_has_entity_name = True
    _attr_name = "Announce TTS"
    _attr_icon = "mdi:speaker-wireless"

    def __init__(self, coordinator: LaxasFitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_announce"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610 (A2DP Speaker)",
        }

    async def async_press(self) -> None:
        """Announce a test message through the watch speaker."""
        _LOGGER.info("Announcing TTS through watch speaker")
        media_player_id = f"media_player.{self.coordinator.config_entry.entry_id}_media_player"
        try:
            await self.hass.services.async_call(
                "tts", "speak",
                {
                    "entity_id": "tts.google_en_com",
                    "media_player_entity_id": media_player_id,
                    "message": "Hello from Home Assistant",
                },
                blocking=False,
            )
        except Exception as err:
            _LOGGER.warning("TTS announce failed: %s", err)
