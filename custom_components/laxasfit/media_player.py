"""Media player entity for LaxasFit BLE Watch."""
from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([LaxasFitMediaPlayer(coordinator, config_entry)])


class LaxasFitMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for LaxasFit watch — browses HA media library."""

    _attr_has_entity_name = True
    _attr_name = "Watch Speaker"
    _attr_icon = "mdi:bluetooth-audio"
    _attr_state = "idle"

    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator: LaxasFitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610 (A2DP + HFP)",
        }
        self._process: asyncio.subprocess.Process | None = None

    # ── Playback ─────────────────────────────────────────────────

    async def async_media_play(self) -> None:
        await self.coordinator.ble.music_control("play")
        self._attr_state = "playing"
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        await self.coordinator.ble.music_control("pause")
        self._attr_state = "paused"
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            self._process = None
        await self.coordinator.ble.music_control("pause")
        self._attr_state = "idle"
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        await self.coordinator.ble.music_control("next")

    async def async_media_previous_track(self) -> None:
        await self.coordinator.ble.music_control("prev")

    # ── Volume ───────────────────────────────────────────────────

    async def async_set_volume_level(self, volume: float) -> None:
        pct = int(volume * 100)
        await self.coordinator.ble.set_volume(pct)
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        current = self.volume_level or 0.5
        await self.async_set_volume_level(min(1.0, current + 0.1))

    async def async_volume_down(self) -> None:
        current = self.volume_level or 0.5
        await self.async_set_volume_level(max(0.0, current - 0.1))

    async def async_mute_volume(self, mute: bool) -> None:
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    # ── Browse (delegates to HA media source) ────────────────────

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: (
                item.media_content_type.startswith("audio/")
                or item.media_content_type.startswith("video/")
            ),
        )

    # ── Play (resolves media source URL + plays via mpv/BLE) ────

    async def async_play_media(
        self,
        media_type: MediaType | str | None = None,
        media_content_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        if media_source.is_media_source_id(media_content_id):
            media_item = await media_source.async_resolve_media(
                self.hass, media_content_id, self.entity_id
            )
            url = media_item.url
            _LOGGER.info("Playing resolved media: %s", url)
        else:
            url = media_content_id
            _LOGGER.info("Playing direct URL: %s", url)

        # Kill previous playback
        if self._process and self._process.returncode is None:
            self._process.terminate()

        # Play via mpv (streams to default audio output = BT speaker if configured)
        if shutil.which("mpv"):
            self._process = await asyncio.create_subprocess_exec(
                "mpv", "--no-video", url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        else:
            # Fallback: send play via BLE
            await self.coordinator.ble.music_control("play")

        self._attr_state = "playing"
        self.async_write_ha_state()
