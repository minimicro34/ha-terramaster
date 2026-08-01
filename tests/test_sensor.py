"""Tests for dynamic TerraMaster storage sensors."""

from unittest.mock import Mock, patch

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terramaster.const import CONF_SHARE_TOKEN, DOMAIN
from custom_components.terramaster.coordinator import TerraMasterDataUpdateCoordinator
from custom_components.terramaster.models import (
    TerraMasterCpuCore,
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterRaid,
    TerraMasterService,
    TerraMasterShare,
    TerraMasterVolume,
)
from custom_components.terramaster.sensor import async_setup_entry


async def test_dynamic_storage_devices(hass: HomeAssistant) -> None:
    """Disks, arrays and volumes create child devices and entities."""
    data = TerraMasterData(
        hostname="NAS-NICO",
        model="F2-221",
        platform="Realtek_RTD1296",
        tos_version="4.2",
        linux_distribution="OpenWrt Chaos Calmer 15.05.1",
        kernel_version="4.4.18",
        uptime=86400,
        boot_time=1785350000,
        cpu_model="ARMv8 Processor rev 4",
        cpu_usage=10.0,
        memory_total=1_000_000_000,
        memory_available=600_000_000,
        memory_usage=40.0,
        temperature=42.0,
        disk_usage=46.0,
        disks=(
            TerraMasterDisk(
                name="sda",
                model="USB DISK 2.0",
                serial=None,
                size=125829120,
                state="running",
                is_system=True,
            ),
            TerraMasterDisk(
                name="sdb",
                model="WDC WD10EFRX",
                serial=None,
                size=1000204886016,
                state="running",
                smart_status="passed",
                temperature=39.0,
                power_on_hours=93148,
                reallocated_sectors=2,
            ),
        ),
        raids=(
            TerraMasterRaid(
                name="md0",
                level="raid1",
                state="clean",
                size=994648784896,
                members=("sdb4", "sdc4"),
                expected_devices=2,
                active_devices=2,
                degraded_devices=0,
            ),
        ),
        volumes=(
            TerraMasterVolume(
                name="vg0-lv0",
                device="/dev/mapper/vg0-lv0",
                filesystem="btrfs",
                mountpoint="/mnt/md0",
                size=994645639168,
                used=454682353664,
                available=536612429824,
                usage=46.0,
            ),
        ),
        cpu_cores=(
            TerraMasterCpuCore(name="cpu0", usage=12.5),
            TerraMasterCpuCore(name="cpu1", usage=25.0),
        ),
        shares=(
            TerraMasterShare(
                name="public",
                path="/mnt/md0/public",
                device="/dev/mapper/vg0-lv0",
                share_type="public",
                hidden=False,
                recycle_bin=True,
                protocols=("smb", "nfs"),
            ),
        ),
        services=(
            TerraMasterService(
                name="ssh", enabled=True, ports=(9222,), protocols=("tcp",)
            ),
            TerraMasterService(
                name="telnet", enabled=True, ports=(23,), protocols=("tcp",)
            ),
            TerraMasterService(name="snmp", enabled=False, ports=(), protocols=()),
        ),
    )
    coordinator = TerraMasterDataUpdateCoordinator(hass, Mock())
    coordinator.async_set_updated_data(data)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NAS-NICO",
        data={
            CONF_HOST: "nas.local",
            CONF_PORT: 9222,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SHARE_TOKEN: "test-share-token",
        },
        unique_id="nas.local:9222",
    )
    entry.runtime_data = coordinator
    entities = []
    registry = er.async_get(hass)
    uptime_registry_entry = registry.async_get_or_create(
        "sensor", DOMAIN, "nas.local:9222_uptime"
    )
    memory_total_registry_entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "nas.local:9222_memory_total",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    received_registry_entry = registry.async_get_or_create(
        "sensor", DOMAIN, "nas.local:9222_network_eth0_received_bytes"
    )
    sent_registry_entry = registry.async_get_or_create(
        "sensor", DOMAIN, "nas.local:9222_network_eth0_sent_bytes"
    )
    registry.async_update_entity_options(
        uptime_registry_entry.entity_id,
        "sensor.private",
        {"suggested_unit_of_measurement": UnitOfTime.SECONDS},
    )
    registry.async_update_entity_options(
        sent_registry_entry.entity_id,
        "sensor",
        {"unit_of_measurement": UnitOfInformation.BYTES},
    )

    try:
        with patch(
            "custom_components.terramaster.sensor.get_url",
            return_value="https://ha.example",
        ):
            await async_setup_entry(hass, entry, entities.extend)

        migrated_uptime = registry.async_get(uptime_registry_entry.entity_id)
        assert migrated_uptime is not None
        assert migrated_uptime.options["sensor.private"] == {
            "suggested_unit_of_measurement": UnitOfTime.DAYS
        }
        migrated_memory_total = registry.async_get(
            memory_total_registry_entry.entity_id
        )
        assert migrated_memory_total is not None
        assert migrated_memory_total.entity_category is None
        migrated_received = registry.async_get(received_registry_entry.entity_id)
        assert migrated_received is not None
        assert migrated_received.options["sensor.private"] == {
            "suggested_unit_of_measurement": UnitOfInformation.GIGABYTES
        }
        migrated_sent = registry.async_get(sent_registry_entry.entity_id)
        assert migrated_sent is not None
        assert migrated_sent.options["sensor"] == {
            "unit_of_measurement": UnitOfInformation.BYTES
        }
        assert "sensor.private" not in migrated_sent.options

        device_names = {
            entity.device_info["name"]
            for entity in entities
            if entity.device_info is not None
        }
        assert "System disk sda" in device_names
        assert "DISK sdb" in device_names
        assert "RAID md0" in device_names
        assert "VOLUME vg0-lv0" in device_names
        assert not any(name.startswith("SHARE") for name in device_names)
        assert (
            sum(
                entity.unique_id.endswith(("cpu0_usage", "cpu1_usage"))
                for entity in entities
                if entity.unique_id is not None
            )
            == 2
        )

        shares_page_entity = next(
            entity
            for entity in entities
            if entity.unique_id is not None
            and entity.unique_id.endswith("shared_folders_page")
        )
        assert shares_page_entity.native_value == 1
        assert shares_page_entity.extra_state_attributes == {
            "shares": ["public"],
            "protocols": ["nfs", "smb"],
            "open_shares": (
                "https://ha.example/api/terramaster/share?"
                f"entry_id={entry.entry_id}&token=test-share-token"
            ),
        }

        share_entity = next(
            entity
            for entity in entities
            if entity.unique_id is not None
            and entity.unique_id.endswith("share_public")
        )
        assert share_entity.device_info["name"] == "NAS-NICO"
        assert share_entity.device_info["configuration_url"] == (
            "https://ha.example/api/terramaster/share?"
            f"entry_id={entry.entry_id}&token=test-share-token"
        )
        assert share_entity.native_value == "/mnt/md0/public"

        with patch(
            "custom_components.terramaster.sensor.get_url",
            return_value="https://ha.example",
        ):
            attributes = share_entity.extra_state_attributes

        assert attributes is not None
        assert attributes["smb_url"] == "smb://admin@nas.local/public"
        assert attributes["nfs_url"] == "nfs://nas.local/mnt/md0/public"
        assert attributes["volume"] == "vg0-lv0"
        assert attributes["filesystem"] == "btrfs"
        assert attributes["capacity_gb"] == 994.65
        assert attributes["used_gb"] == 454.68
        assert attributes["available_gb"] == 536.61
        assert "capacity_bytes" not in attributes
        assert "used_bytes" not in attributes
        assert "available_bytes" not in attributes
        assert attributes["raid"] == "md0"
        assert attributes["raid_level"] == "raid1"
        assert attributes["open_share"] == (
            "https://ha.example/api/terramaster/share?"
            f"entry_id={entry.entry_id}"
            "&token=test-share-token"
            "&share=public"
        )
        assert "afp_url" not in attributes
    finally:
        await coordinator.async_shutdown()
