"""DataUpdateCoordinator for LaxasFit BLE Watch."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .ble_protocol import LaxasFitBLE, WatchState
from .const import DOMAIN, CMD_SPORT, CMD_DEV_CTRL, CMD_DEV_SETTING

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


class LaxasFitCoordinator(DataUpdateCoordinator[WatchState]):
    """Coordinator that polls the watch for sensor data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, ble: LaxasFitBLE
    ) -> None:
        self.ble = ble
        self.entry = entry
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> WatchState:
        if not self.ble.connected:
            raise UpdateFailed("Watch not connected")

        try:
            await self.ble.read_battery()
            await self.ble.request_sport_data(1)
            await self.ble.sync_time()
        except Exception as err:
            raise UpdateFailed(f"Error polling watch: {err}") from err

        return self.ble.state
