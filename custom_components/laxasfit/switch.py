"""Switch entities for LaxasFit BLE Watch settings."""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LaxasFitSwitchEntityDescription(SwitchEntityDescription):
    turn_on_fn: Callable[..., Coroutine[Any, Any, Any]]
    turn_off_fn: Callable[..., Coroutine[Any, Any, Any]]
    is_on_fn: Callable[..., bool]


async def _set_hr(ble, on: bool) -> None:
    await ble.send_command(14 if on else 14, 0)


async def _set_sedentary(ble, on: bool) -> None:
    await ble.set_sedentary_reminder(on)


async def _set_drink(ble, on: bool) -> None:
    await ble.set_drink_reminder(on)


async def _set_hr_auto(ble, on: bool) -> None:
    await ble.set_hr_auto_measure(on)


SWITCH_DESCRIPTIONS: tuple[LaxasFitSwitchEntityDescription, ...] = (
    LaxasFitSwitchEntityDescription(
        key="sedentary",
        name="Sedentary Reminder",
        icon="mdi:chair-rolling",
        turn_on_fn=lambda ble: ble.set_sedentary_reminder(True),
        turn_off_fn=lambda ble: ble.set_sedentary_reminder(False),
        is_on_fn=lambda ble: False,
    ),
    LaxasFitSwitchEntityDescription(
        key="drink_reminder",
        name="Drink Reminder",
        icon="mdi:cup-water",
        turn_on_fn=lambda ble: ble.set_drink_reminder(True),
        turn_off_fn=lambda ble: ble.set_drink_reminder(False),
        is_on_fn=lambda ble: False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [LaxasFitSwitch(coordinator, entry, d) for d in SWITCH_DESCRIPTIONS]
    async_add_entities(entities)


class LaxasFitSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    entity_description: LaxasFitSwitchEntityDescription

    def __init__(
        self,
        coordinator: LaxasFitCoordinator,
        entry: ConfigEntry,
        description: LaxasFitSwitchEntityDescription,
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

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.ble)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.turn_on_fn(self.coordinator.ble)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.turn_off_fn(self.coordinator.ble)
