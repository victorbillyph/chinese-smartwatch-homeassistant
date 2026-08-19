"""Media player entity for LaxasFit BLE Watch with A2DP/BT Classic support.

The watch acts as a Bluetooth speaker (A2DP) + microphone (HFP).
When paired via BT Classic, audio routes through the watch speaker.
This entity controls both BLE media keys and PulseAudio volume.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media,
)
from homeassistant.components.media_source import (
    MediaSource,
    MediaSourceItem,
    UnresolvedMediaSourceIdentifier,
    browse_media,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([LaxasFitMediaPlayer(coordinator, entry)])


def _run_pactl(*args: str) -> str | None:
    """Run a pactl command and return stdout, or None on failure."""
    if not shutil.which("pactl"):
        return None
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _find_pactl_sink(bt_address: str) -> str | None:
    """Find the PulseAudio sink name for the BT device."""
    output = _run_pactl("list", "sinks", "short")
    if not output:
        return None
    addr_normalized = bt_address.replace(":", "-").lower()
    for line in output.splitlines():
        if addr_normalized in line.lower():
            return line.split()[0]
    return None


class LaxasFitMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player for LaxasFit watch.

    Routes audio through the watch speaker via BT Classic (A2DP).
    Falls back to BLE-only media key control if BT Classic is unavailable.
    """

    _attr_has_entity_name = True
    _attr_name = "Watch Speaker"
    _attr_supported_features = SUPPORT_FLAGS
    _attr_state = MediaPlayerState.IDLE
    _attr_icon = "mdi:bluetooth-audio"

    def __init__(self, coordinator: LaxasFitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610 (A2DP + HFP)",
        }
        self._sink_name: str | None = None
        self._bt_address = coordinator.ble.state.bt_classic_address

    def _resolve_sink(self) -> str | None:
        """Find or cache the PulseAudio sink for this watch."""
        if self._sink_name:
            return self._sink_name
        if self._bt_address:
            self._sink_name = _find_pactl_sink(self._bt_address)
        return self._sink_name

    @property
    def volume_level(self) -> float | None:
        sink = self._resolve_sink()
        if not sink:
            return None
        output = _run_pactl("get-sink-volume", sink)
        if output and "/" in output:
            try:
                pct = output.split("/")[1].strip().replace("%", "")
                return int(pct) / 100.0
            except (ValueError, IndexError):
                pass
        return None

    @property
    def is_volume_muted(self) -> bool | None:
        sink = self._resolve_sink()
        if not sink:
            return None
        output = _run_pactl("get-sink-mute", sink)
        if output and "yes" in output.lower():
            return True
        if output and "no" in output.lower():
            return False
        return None

    async def async_media_play(self) -> None:
        await self.coordinator.ble.music_control("play")
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        await self.coordinator.ble.music_control("pause")
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        await self.coordinator.ble.music_control("next")

    async def async_media_previous_track(self) -> None:
        await self.coordinator.ble.music_control("prev")

    async def async_set_volume_level(self, volume: float) -> None:
        pct = int(volume * 100)
        sink = self._resolve_sink()
        if sink:
            await asyncio.to_thread(_run_pactl, "set-sink-volume", sink, str(pct))
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
        sink = self._resolve_sink()
        if sink:
            state = "on" if mute else "off"
            await asyncio.to_thread(_run_pactl, "set-sink-mute", sink, state)
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_browse_media(
        self, media_content_id: str | None = None, media_content_type: str | None = None
    ) -> BrowseMedia:
        """Browse media from HA media source."""
        return await browse_media(
            self.hass,
            f"{media_content_type or 'music'}/{media_content_id or ''}",
        )

    async def async_play_media(
        self, media_type: str | None, media_id: str | None, **kwargs
    ) -> None:
        """Play media through the watch speaker (BT A2DP)."""
        if not media_id:
            _LOGGER.warning("No media ID provided")
            return

        _LOGGER.info("Playing media: %s/%s", media_type, media_id)

        # If it's a media source URI, resolve and play via PulseAudio
        if media_id.startswith("media-source://"):
            try:
                resolved = await async_process_play_media(
                    self.hass, media_type or "music", media_id
                )
                # Play via local media (mpv/gstreamer to BT sink)
                sink = self._resolve_sink()
                if sink:
                    cmd = [
                        "mpv", "--no-video",
                        f"--audio-device=pulse/{sink}",
                        resolved.url,
                    ]
                    asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                else:
                    _LOGGER.warning("BT sink not found, cannot route audio")
            except Exception as err:
                _LOGGER.error("Failed to play media source: %s", err)
        else:
            # Direct URL - play via mpv to BT sink
            sink = self._resolve_sink()
            if sink:
                cmd = [
                    "mpv", "--no-video",
                    f"--audio-device=pulse/{sink}",
                    media_id,
                ]
                asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            else:
                # Fallback: just send play command via BLE
                await self.coordinator.ble.music_control("play")

        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()
