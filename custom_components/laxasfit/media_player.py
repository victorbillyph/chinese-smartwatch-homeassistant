"""Media player entity for LaxasFit BLE Watch."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from typing import Any

from homeassistant.components.media_player import (
    BrowseError,
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


def _run_cmd(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


class LaxasFitMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for LaxasFit watch — controls phone media via BLE."""

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

    # ── Playback controls (BLE) ──────────────────────────────────

    async def async_media_play(self) -> None:
        await self.coordinator.ble.music_control("play")
        self._attr_state = "playing"
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        await self.coordinator.ble.music_control("pause")
        self._attr_state = "paused"
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        await self.coordinator.ble.music_control("pause")
        self._attr_state = "idle"
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        await self.coordinator.ble.music_control("next")

    async def async_media_previous_track(self) -> None:
        await self.coordinator.ble.music_control("prev")

    # ── Volume (PulseAudio fallback) ─────────────────────────────

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

    # ── Media browsing ───────────────────────────────────────────

    async def async_browse_media(
        self,
        media_content_type: str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        # Root level
        if media_content_id is None:
            return BrowseMedia(
                title="Watch Speaker",
                media_class="library",
                media_content_id="root",
                media_content_type="library",
                can_play=False,
                can_expand=True,
                children=[
                    BrowseMedia(
                        title="Phone Music",
                        media_class="music",
                        media_content_id="phone_music",
                        media_content_type="music",
                        can_play=True,
                        can_expand=False,
                        thumbnail="https://brands.home-assistant.io/_/multimedia/logo.png",
                    ),
                    BrowseMedia(
                        title="Radio (SomaFM)",
                        media_class="channel",
                        media_content_id="radio_somafm",
                        media_content_type="music",
                        can_play=True,
                        can_expand=False,
                        thumbnail="https://somafm.com/img3/sqml-1400.jpg",
                    ),
                    BrowseMedia(
                        title="TTS Test",
                        media_class="music",
                        media_content_id="tts_test",
                        media_content_type="music",
                        can_play=True,
                        can_expand=False,
                        thumbnail="https://brands.home-assistant.io/_/tts/logo.png",
                    ),
                ],
            )

        raise BrowseError(f"Media not found: {media_content_id}")

    # ── Play media ───────────────────────────────────────────────

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_content_id: str,
        **kwargs: Any,
    ) -> None:
        _LOGGER.info("Playing media: %s (%s)", media_content_id, media_type)

        if media_content_id == "phone_music":
            # Just send play command — phone handles the rest
            await self.coordinator.ble.music_control("play")
            self._attr_state = "playing"
            self.async_write_ha_state()

        elif media_content_id == "radio_somafm":
            # Play SomaFM Groove Salad via mpv (streams to default audio output)
            url = "https://somafm.com/groovesalad.mp3"
            if shutil.which("mpv"):
                asyncio.create_subprocess_exec(
                    "mpv", "--no-video", url,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            else:
                # Fallback: send play via BLE
                await self.coordinator.ble.music_control("play")
            self._attr_state = "playing"
            self.async_write_ha_state()

        elif media_content_id == "tts_test":
            # Use HA TTS via command line
            if shutil.which("mpv"):
                asyncio.create_subprocess_exec(
                    "mpv", "--no-video",
                    "https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q=Hello+from+Home+Assistant",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            self._attr_state = "playing"
            self.async_write_ha_state()

        else:
            # Direct URL — play via mpv
            if shutil.which("mpv"):
                asyncio.create_subprocess_exec(
                    "mpv", "--no-video", media_content_id,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            self._attr_state = "playing"
            self.async_write_ha_state()
