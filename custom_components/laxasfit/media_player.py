"""Media player entity for LaxasFit BLE Watch."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
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
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([LaxasFitMediaPlayer(coordinator, entry)])


def _run_pactl(*args: str) -> str | None:
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
    output = _run_pactl("list", "sinks", "short")
    if not output:
        return None
    addr_normalized = bt_address.replace(":", "-").lower()
    for line in output.splitlines():
        if addr_normalized in line.lower():
            return line.split()[0]
    return None


class LaxasFitMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
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
