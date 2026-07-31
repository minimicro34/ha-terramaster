"""Sensor platform for TerraMaster TOS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TerraMasterConfigEntry
from .const import DOMAIN
from .coordinator import TerraMasterDataUpdateCoordinator
from .models import (
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterRaid,
    TerraMasterVolume,
)


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
        key="last_restart",
        translation_key="last_restart",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            datetime.fromtimestamp(data.boot_time, tz=UTC)
            if data.boot_time is not None
            else None
        ),
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
    known: set[tuple[str, str, str]] = set()

    def async_discover_storage() -> None:
        entities: list[TerraMasterStorageSensor] = []
        for kind, objects, descriptions in (
            ("disk", entry.runtime_data.data.disks, DISK_SENSORS),
            ("raid", entry.runtime_data.data.raids, RAID_SENSORS),
            ("volume", entry.runtime_data.data.volumes, VOLUME_SENSORS),
        ):
            for storage_object in objects:
                for description in descriptions:
                    key = (kind, storage_object.name, description.key)
                    if key not in known:
                        known.add(key)
                        entities.append(
                            TerraMasterStorageSensor(
                                entry.runtime_data,
                                entry,
                                kind,
                                storage_object.name,
                                description,
                            )
                        )
        if entities:
            async_add_entities(entities)

    async_discover_storage()
    entry.async_on_unload(entry.runtime_data.async_add_listener(async_discover_storage))


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


@dataclass(frozen=True, kw_only=True)
class TerraMasterStorageSensorDescription(SensorEntityDescription):
    """Describe a sensor attached to a storage object."""

    value_fn: Callable[[Any], Any]


def _attribute_value(storage_object: Any, *, attribute: str) -> object:
    """Return a named attribute from a storage data object."""
    return getattr(storage_object, attribute)


DISK_SENSORS: tuple[TerraMasterStorageSensorDescription, ...] = (
    TerraMasterStorageSensorDescription(
        key="role",
        translation_key="storage_role",
        icon="mdi:tag-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: "system" if disk.is_system else "user",
    ),
    TerraMasterStorageSensorDescription(
        key="model",
        translation_key="disk_model",
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.model,
    ),
    TerraMasterStorageSensorDescription(
        key="size",
        translation_key="capacity",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.size,
    ),
    TerraMasterStorageSensorDescription(
        key="state",
        translation_key="state",
        icon="mdi:harddisk",
        value_fn=lambda disk: disk.state,
    ),
    TerraMasterStorageSensorDescription(
        key="smart_status",
        translation_key="smart_status",
        icon="mdi:check-decagram",
        value_fn=lambda disk: disk.smart_status,
    ),
    TerraMasterStorageSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: disk.temperature,
    ),
    TerraMasterStorageSensorDescription(
        key="power_on_hours",
        translation_key="power_on_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.power_on_hours,
    ),
    *tuple(
        TerraMasterStorageSensorDescription(
            key=key,
            translation_key=translation_key,
            icon=icon,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=partial(_attribute_value, attribute=key),
        )
        for key, translation_key, icon in (
            ("power_cycle_count", "power_cycles", "mdi:power-cycle"),
            ("start_stop_count", "start_stop_cycles", "mdi:restart"),
            ("load_cycle_count", "load_cycles", "mdi:harddisk-plus"),
            ("spin_retry_count", "spin_retries", "mdi:rotate-3d-variant"),
            ("reallocated_events", "reallocated_events", "mdi:swap-horizontal"),
            ("udma_crc_errors", "udma_crc_errors", "mdi:connection"),
        )
    ),
    TerraMasterStorageSensorDescription(
        key="reallocated_sectors",
        translation_key="reallocated_sectors",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.reallocated_sectors,
    ),
    TerraMasterStorageSensorDescription(
        key="pending_sectors",
        translation_key="pending_sectors",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.pending_sectors,
    ),
    TerraMasterStorageSensorDescription(
        key="offline_uncorrectable",
        translation_key="offline_uncorrectable",
        icon="mdi:alert-octagon-outline",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda disk: disk.offline_uncorrectable,
    ),
)

RAID_SENSORS: tuple[TerraMasterStorageSensorDescription, ...] = (
    TerraMasterStorageSensorDescription(
        key="role",
        translation_key="storage_role",
        icon="mdi:tag-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda raid: "system" if raid.is_system else "user",
    ),
    TerraMasterStorageSensorDescription(
        key="level", translation_key="raid_level", value_fn=lambda raid: raid.level
    ),
    TerraMasterStorageSensorDescription(
        key="state", translation_key="state", value_fn=lambda raid: raid.state
    ),
    TerraMasterStorageSensorDescription(
        key="size",
        translation_key="capacity",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda raid: raid.size,
    ),
    TerraMasterStorageSensorDescription(
        key="degraded_devices",
        translation_key="degraded_devices",
        icon="mdi:harddisk-remove",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda raid: raid.degraded_devices,
    ),
    TerraMasterStorageSensorDescription(
        key="sync_action",
        translation_key="sync_action",
        icon="mdi:sync",
        value_fn=lambda raid: raid.sync_action,
    ),
    TerraMasterStorageSensorDescription(
        key="sync_progress",
        translation_key="sync_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda raid: raid.sync_progress,
    ),
)

VOLUME_SENSORS: tuple[TerraMasterStorageSensorDescription, ...] = (
    TerraMasterStorageSensorDescription(
        key="filesystem",
        translation_key="filesystem",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda volume: volume.filesystem,
    ),
    TerraMasterStorageSensorDescription(
        key="mountpoint",
        translation_key="mountpoint",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda volume: volume.mountpoint,
    ),
    *tuple(
        TerraMasterStorageSensorDescription(
            key=key,
            translation_key=translation_key,
            device_class=SensorDeviceClass.DATA_SIZE,
            native_unit_of_measurement=UnitOfInformation.BYTES,
            suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=partial(_attribute_value, attribute=key),
        )
        for key, translation_key in (
            ("size", "capacity"),
            ("used", "used_space"),
            ("available", "available_space"),
        )
    ),
    TerraMasterStorageSensorDescription(
        key="usage",
        translation_key="disk_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda volume: volume.usage,
    ),
)


class TerraMasterStorageSensor(
    CoordinatorEntity[TerraMasterDataUpdateCoordinator], SensorEntity
):
    """Sensor attached to a dynamically discovered storage device."""

    entity_description: TerraMasterStorageSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TerraMasterDataUpdateCoordinator,
        entry: TerraMasterConfigEntry,
        kind: str,
        object_name: str,
        description: TerraMasterStorageSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._kind = kind
        self._object_name = object_name
        nas_id = entry.unique_id or entry.entry_id
        object_id = f"{nas_id}_{kind}_{object_name}"
        storage_object = self._object()
        is_system = bool(
            storage_object is not None and getattr(storage_object, "is_system", False)
        )
        device_name = (
            f"System {kind} {object_name}"
            if is_system
            else f"{kind.upper()} {object_name}"
        )
        self._attr_unique_id = f"{object_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, object_id)},
            "name": device_name,
            "manufacturer": "TerraMaster",
            "model": f"{'System ' if is_system else ''}{kind.capitalize()}",
            "via_device": (DOMAIN, nas_id),
        }

    def _object(self) -> TerraMasterDisk | TerraMasterRaid | TerraMasterVolume | None:
        objects = getattr(self.coordinator.data, f"{self._kind}s")
        return next((item for item in objects if item.name == self._object_name), None)

    @property
    def available(self) -> bool:
        """Return whether the object and metric are available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> Any:
        """Return the current storage metric."""
        storage_object = self._object()
        if storage_object is None:
            return None
        return self.entity_description.value_fn(storage_object)
