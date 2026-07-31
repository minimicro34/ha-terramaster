"""Sensor platform for TerraMaster TOS."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
    CONF_HOST,
    PERCENTAGE,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TerraMasterConfigEntry
from .const import DOMAIN
from .coordinator import TerraMasterDataUpdateCoordinator
from .models import (
    TerraMasterCpuCore,
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterNetwork,
    TerraMasterRaid,
    TerraMasterService,
    TerraMasterShare,
    TerraMasterVolume,
)
from .share import share_connection_urls, share_page_url


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
        key="platform",
        translation_key="platform",
        icon="mdi:developer-board",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.platform,
    ),
    TerraMasterSensorEntityDescription(
        key="tos_version",
        translation_key="tos_version",
        icon="mdi:package-up",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.tos_version,
    ),
    TerraMasterSensorEntityDescription(
        key="linux_distribution",
        translation_key="linux_distribution",
        icon="mdi:linux",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.linux_distribution,
    ),
    TerraMasterSensorEntityDescription(
        key="kernel_version",
        translation_key="kernel_version",
        icon="mdi:linux",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.kernel_version,
    ),
    TerraMasterSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda data: (
            round(data.uptime / 86400, 2) if data.uptime is not None else None
        ),
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
        key="cpu_model",
        translation_key="cpu_model",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.cpu_model,
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
        key="memory_total",
        translation_key="memory_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        value_fn=lambda data: data.memory_total,
    ),
    TerraMasterSensorEntityDescription(
        key="memory_available",
        translation_key="memory_available",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.memory_available,
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


_SUGGESTED_UNIT_MIGRATIONS = {
    "_uptime": UnitOfTime.DAYS,
    "_power_on_hours": UnitOfTime.DAYS,
    "_receive_rate": UnitOfDataRate.MEGABITS_PER_SECOND,
    "_transmit_rate": UnitOfDataRate.MEGABITS_PER_SECOND,
    "_received_bytes": UnitOfInformation.GIGABYTES,
    "_sent_bytes": UnitOfInformation.GIGABYTES,
}


def _migrate_registry_defaults(hass: HomeAssistant) -> None:
    """Migrate integration defaults without overriding user-selected units."""
    registry = er.async_get(hass)
    for registry_entry in list(registry.entities.values()):
        if registry_entry.platform != DOMAIN:
            continue
        if (
            registry_entry.unique_id.endswith("_memory_total")
            and registry_entry.entity_category == EntityCategory.DIAGNOSTIC
        ):
            registry.async_update_entity(registry_entry.entity_id, entity_category=None)
        if "unit_of_measurement" in registry_entry.options.get("sensor", {}):
            continue
        private_options: Mapping[str, Any] = registry_entry.options.get(
            "sensor.private", {}
        )
        current_unit = private_options.get("suggested_unit_of_measurement")
        for suffix, new_unit in _SUGGESTED_UNIT_MIGRATIONS.items():
            if registry_entry.unique_id.endswith(suffix) and current_unit != new_unit:
                registry.async_update_entity_options(
                    registry_entry.entity_id,
                    "sensor.private",
                    {"suggested_unit_of_measurement": new_unit},
                )
                break


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TerraMaster sensors."""
    _migrate_registry_defaults(hass)
    async_add_entities(
        TerraMasterSensor(entry.runtime_data, entry, description)
        for description in SENSORS
    )
    async_add_entities(
        TerraMasterServiceSensor(entry.runtime_data, entry, service_name)
        for service_name in ("ssh", "telnet", "snmp")
    )
    known: set[tuple[str, str, str]] = set()
    known_cpu_cores: set[str] = set()
    known_shares: set[str] = set()

    def async_discover_entities() -> None:
        entities: list[SensorEntity] = []
        for share in entry.runtime_data.data.shares:
            if share.name not in known_shares:
                known_shares.add(share.name)
                entities.append(
                    TerraMasterShareSensor(entry.runtime_data, entry, share.name)
                )
        for core in entry.runtime_data.data.cpu_cores:
            if core.name not in known_cpu_cores:
                known_cpu_cores.add(core.name)
                entities.append(
                    TerraMasterCpuCoreSensor(entry.runtime_data, entry, core.name)
                )
        for kind, objects, descriptions in (
            ("disk", entry.runtime_data.data.disks, DISK_SENSORS),
            ("raid", entry.runtime_data.data.raids, RAID_SENSORS),
            ("volume", entry.runtime_data.data.volumes, VOLUME_SENSORS),
            ("network", entry.runtime_data.data.networks, NETWORK_SENSORS),
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

    async_discover_entities()
    entry.async_on_unload(
        entry.runtime_data.async_add_listener(async_discover_entities)
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


CPU_CORE_SENSOR = SensorEntityDescription(
    key="cpu_core_usage",
    translation_key="cpu_core_usage",
    icon="mdi:cpu-64-bit",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
)


class TerraMasterCpuCoreSensor(
    CoordinatorEntity[TerraMasterDataUpdateCoordinator], SensorEntity
):
    """Utilization sensor for a dynamically discovered logical CPU core."""

    entity_description = CPU_CORE_SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TerraMasterDataUpdateCoordinator,
        entry: TerraMasterConfigEntry,
        core_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._core_name = core_name
        nas_id = entry.unique_id or entry.entry_id
        core_number = core_name.removeprefix("cpu")
        display_number = (
            str(int(core_number) + 1) if core_number.isdigit() else core_name
        )
        self._attr_unique_id = f"{nas_id}_{core_name}_usage"
        self._attr_translation_placeholders = {"core": display_number}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, nas_id)},
            "name": coordinator.data.hostname,
            "manufacturer": "TerraMaster",
            "model": coordinator.data.model,
            "sw_version": coordinator.data.tos_version,
        }

    def _core(self) -> TerraMasterCpuCore | None:
        return next(
            (
                core
                for core in self.coordinator.data.cpu_cores
                if core.name == self._core_name
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Return whether the core utilization sample is available."""
        core = self._core()
        return super().available and core is not None and core.usage is not None

    @property
    def native_value(self) -> float | None:
        """Return the current logical CPU utilization."""
        core = self._core()
        return core.usage if core is not None else None


SERVICE_SENSOR = SensorEntityDescription(
    key="service_status",
    translation_key="service_status",
    device_class=SensorDeviceClass.ENUM,
    options=["enabled", "disabled"],
    icon="mdi:server-network",
    entity_category=EntityCategory.DIAGNOSTIC,
)


class TerraMasterServiceSensor(
    CoordinatorEntity[TerraMasterDataUpdateCoordinator], SensorEntity
):
    """Status and listening ports for a TOS management service."""

    entity_description = SERVICE_SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TerraMasterDataUpdateCoordinator,
        entry: TerraMasterConfigEntry,
        service_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._service_name = service_name
        nas_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{nas_id}_{service_name}_service"
        self._attr_translation_placeholders = {"service": service_name.upper()}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, nas_id)},
            "name": coordinator.data.hostname,
            "manufacturer": "TerraMaster",
            "model": coordinator.data.model,
            "sw_version": coordinator.data.tos_version,
        }

    def _service(self) -> TerraMasterService | None:
        return next(
            (
                service
                for service in self.coordinator.data.services
                if service.name == self._service_name
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Return whether service detection was available."""
        service = self._service()
        return super().available and service is not None and service.enabled is not None

    @property
    def native_value(self) -> str | None:
        """Return enabled or disabled."""
        service = self._service()
        if service is None or service.enabled is None:
            return None
        return "enabled" if service.enabled else "disabled"

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return listening port and protocol details."""
        service = self._service()
        if service is None:
            return None
        return {"ports": list(service.ports), "protocols": list(service.protocols)}


SHARE_SENSOR = SensorEntityDescription(
    key="shared_folder",
    translation_key="shared_folder",
    icon="mdi:folder-network",
    entity_category=EntityCategory.DIAGNOSTIC,
)


class TerraMasterShareSensor(
    CoordinatorEntity[TerraMasterDataUpdateCoordinator], SensorEntity
):
    """A TOS shared folder attached to the main NAS device."""

    entity_description = SHARE_SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TerraMasterDataUpdateCoordinator,
        entry: TerraMasterConfigEntry,
        share_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._share_name = share_name
        self._home_assistant = coordinator.hass
        self._host = str(entry.data[CONF_HOST])
        self._entry_id = entry.entry_id
        nas_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{nas_id}_share_{share_name}"
        self._attr_translation_placeholders = {"share": share_name}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, nas_id)},
            "name": coordinator.data.hostname,
            "manufacturer": "TerraMaster",
            "model": coordinator.data.model,
            "sw_version": coordinator.data.tos_version,
        }

    def _share(self) -> TerraMasterShare | None:
        return next(
            (
                share
                for share in self.coordinator.data.shares
                if share.name == self._share_name
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Return whether the shared folder still exists."""
        return super().available and self._share() is not None

    @property
    def native_value(self) -> str | None:
        """Return the shared-folder path."""
        share = self._share()
        return share.path if share is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return shared-folder details."""
        share = self._share()
        if share is None:
            return None
        attributes: dict[str, object] = {
            "device": share.device,
            "type": share.share_type,
            "hidden": share.hidden,
            "recycle_bin": share.recycle_bin,
            "protocols": list(share.protocols),
        }
        urls = share_connection_urls(self._host, share)
        attributes.update({f"{protocol}_url": url for protocol, url in urls.items()})
        if urls:
            try:
                base_url = get_url(self._home_assistant, prefer_external=True)
            except NoURLAvailableError:
                pass
            else:
                attributes["open_share"] = share_page_url(
                    base_url, self._entry_id, share.name
                )
        return attributes


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
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda disk: (
            round(disk.power_on_hours / 24, 2)
            if disk.power_on_hours is not None
            else None
        ),
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

NETWORK_SENSORS: tuple[TerraMasterStorageSensorDescription, ...] = (
    TerraMasterStorageSensorDescription(
        key="state",
        translation_key="link_state",
        icon="mdi:lan-connect",
        value_fn=lambda network: network.state,
    ),
    TerraMasterStorageSensorDescription(
        key="speed",
        translation_key="link_speed",
        icon="mdi:speedometer",
        native_unit_of_measurement="Mbit/s",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda network: network.speed,
    ),
    *tuple(
        TerraMasterStorageSensorDescription(
            key=key,
            translation_key=translation_key,
            device_class=SensorDeviceClass.DATA_SIZE,
            native_unit_of_measurement=UnitOfInformation.BYTES,
            suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=partial(_attribute_value, attribute=key),
        )
        for key, translation_key in (
            ("received_bytes", "received_data"),
            ("sent_bytes", "sent_data"),
        )
    ),
    *tuple(
        TerraMasterStorageSensorDescription(
            key=key,
            translation_key=translation_key,
            device_class=SensorDeviceClass.DATA_RATE,
            native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=3,
            value_fn=partial(_attribute_value, attribute=key),
        )
        for key, translation_key in (
            ("receive_rate", "receive_rate"),
            ("transmit_rate", "transmit_rate"),
        )
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

    def _object(
        self,
    ) -> (
        TerraMasterDisk
        | TerraMasterRaid
        | TerraMasterVolume
        | TerraMasterNetwork
        | None
    ):
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
