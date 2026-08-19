"""Sensor entities for LaxasFit BLE Watch."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaxasFitCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LaxasFitSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[LaxasFitCoordinator], float | int | None]


SENSOR_DESCRIPTIONS: tuple[LaxasFitSensorEntityDescription, ...] = (
    LaxasFitSensorEntityDescription(
        key="steps",
        name="Steps",
        icon="mdi:walk",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="steps",
        value_fn=lambda c: c.ble.state.steps,
    ),
    LaxasFitSensorEntityDescription(
        key="distance",
        name="Distance",
        icon="mdi:map-marker-distance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda c: c.ble.state.distance,
    ),
    LaxasFitSensorEntityDescription(
        key="calories",
        name="Calories",
        icon="mdi:fire",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kcal",
        value_fn=lambda c: c.ble.state.calories,
    ),
    LaxasFitSensorEntityDescription(
        key="heart_rate",
        name="Heart Rate",
        icon="mdi:heart-pulse",
        device_class=SensorDeviceClass.HEART_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="bpm",
        value_fn=lambda c: c.ble.state.heart_rate,
    ),
    LaxasFitSensorEntityDescription(
        key="blood_pressure_sys",
        name="Blood Pressure Systolic",
        icon="mdi:heart",
        device_class=SensorDeviceClass.BLOOD_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mmHg",
        value_fn=lambda c: c.ble.state.blood_pressure_sys,
    ),
    LaxasFitSensorEntityDescription(
        key="blood_pressure_dia",
        name="Blood Pressure Diastolic",
        icon="mdi:heart",
        device_class=SensorDeviceClass.BLOOD_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mmHg",
        value_fn=lambda c: c.ble.state.blood_pressure_dia,
    ),
    LaxasFitSensorEntityDescription(
        key="spo2",
        name="Blood Oxygen",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.OXYGEN_SATURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=lambda c: c.ble.state.spo2,
    ),
    LaxasFitSensorEntityDescription(
        key="temperature",
        name="Body Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        value_fn=lambda c: c.ble.state.temperature,
    ),
    LaxasFitSensorEntityDescription(
        key="battery",
        name="Battery",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        value_fn=lambda c: c.ble.state.battery,
    ),
    LaxasFitSensorEntityDescription(
        key="deep_sleep",
        name="Deep Sleep",
        icon="mdi:sleep",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        value_fn=lambda c: c.ble.state.deep_sleep_min,
    ),
    LaxasFitSensorEntityDescription(
        key="light_sleep",
        name="Light Sleep",
        icon="mdi:sleep",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="min",
        value_fn=lambda c: c.ble.state.light_sleep_min,
    ),
    LaxasFitSensorEntityDescription(
        key="wake_count",
        name="Wake Count",
        icon="mdi:eye",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="times",
        value_fn=lambda c: c.ble.state.wake_count,
    ),
    LaxasFitSensorEntityDescription(
        key="sport_mode",
        name="Sport Mode",
        icon="mdi:run",
        value_fn=lambda c: c.ble.state.sport_mode,
    ),
    LaxasFitSensorEntityDescription(
        key="sport_duration",
        name="Sport Duration",
        icon="mdi:timer",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",
        value_fn=lambda c: c.ble.state.sport_duration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: LaxasFitCoordinator = data["coordinator"]

    entities = []
    for desc in SENSOR_DESCRIPTIONS:
        entities.append(
            LaxasFitSensor(coordinator, entry, desc)
        )

    async_add_entities(entities)


class LaxasFitSensor(CoordinatorEntity[LaxasFitCoordinator], SensorEntity):
    """Sensor entity for LaxasFit watch."""

    _attr_has_entity_name = True
    entity_description: LaxasFitSensorEntityDescription

    def __init__(
        self,
        coordinator: LaxasFitCoordinator,
        entry: ConfigEntry,
        description: LaxasFitSensorEntityDescription,
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
    def native_value(self) -> float | int | None:
        return self.entity_description.value_fn(self.coordinator)
