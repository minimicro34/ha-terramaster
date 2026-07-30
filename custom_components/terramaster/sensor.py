"""Sensor platform for TerraMaster TOS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TerraMasterConfigEntry
from .coordinator import TerraMasterDataUpdateCoordinator
from .models import TerraMasterData


@dataclass(frozen=True, kw_only=True)
class TerraMasterSensorEntityDescription(SensorEntityDescription):
    """Describe a TerraMaster sensor."""

    value_fn: Callable[[TerraMasterData], Any]


SENSORS: tuple[TerraMasterSensorEntityDescription, ...] = (
    TerraMasterSensorEntityDescription(
        key="model",
        translation_key="model",
        icon="mdi:nas",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.model,
    ),
    TerraMasterSensorEntityDescription(
        key="tos_version",
        translation_key="tos_version",
        icon="mdi:package-up",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.tos_version,
    ),
    TerraMasterSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda data: data.uptime,
    ),
    TerraMasterSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        icon="mdi:cpu-64-bit",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.cpu_usage,
    ),
    TerraMasterSensorEntityDescription(
        key="memory_usage",
        translation_key="memory_usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.memory_usage,
    ),
    TerraMasterSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.temperature,
    ),
    TerraMasterSensorEntityDescription(
        key="disk_usage",
        translation_key="disk_usage",
        icon="mdi:harddisk",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.disk_usage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TerraMaster sensors."""
    async_add_entities(
        TerraMasterSensor(entry.runtime_data, entry, description)
        for description in SENSORS
    )


class TerraMasterSensor(
    CoordinatorEntity[TerraMasterDataUpdateCoordinator], SensorEntity
):
    """Representation of a TerraMaster sensor."""

    entity_description: TerraMasterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TerraMasterDataUpdateCoordinator,
        entry: TerraMasterConfigEntry,
        description: TerraMasterSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {("terramaster", device_id)},
            "name": coordinator.data.hostname,
            "manufacturer": "TerraMaster",
            "model": coordinator.data.model,
            "sw_version": coordinator.data.tos_version,
        }

    @property
    def available(self) -> bool:
        """Return whether this particular metric is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
