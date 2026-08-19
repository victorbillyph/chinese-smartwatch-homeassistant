"""Number entities for LaxasFit BLE Watch settings."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([
        LaxasFitStepTarget(coordinator, entry),
    ])


class LaxasFitStepTarget(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Step Target"
    _attr_icon = "mdi:walk"
    _attr_native_min_value = 1000
    _attr_native_max_value = 50000
    _attr_native_step = 500
    _attr_native_value = 5000
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: LaxasFitCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_step_target"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get("name", "Watch"),
            "manufacturer": "LaxasFit / Bluetrum",
            "model": "AB5610",
        }

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.ble.set_step_target(int(value))
        self._attr_native_value = int(value)
        self.async_write_ha_state()
