"""Tests for dynamic TerraMaster storage sensors."""

from unittest.mock import Mock

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terramaster.const import DOMAIN
from custom_components.terramaster.coordinator import TerraMasterDataUpdateCoordinator
from custom_components.terramaster.models import (
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterRaid,
    TerraMasterVolume,
)
from custom_components.terramaster.sensor import async_setup_entry


async def test_dynamic_storage_devices(hass: HomeAssistant) -> None:
    """Disks, arrays and volumes create child devices and entities."""
    data = TerraMasterData(
        hostname="NAS-NICO",
        model="F2-221",
        tos_version="4.2",
        uptime=86400,
        boot_time=1785350000,
        cpu_usage=10.0,
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
        },
        unique_id="nas.local:9222",
    )
    entry.runtime_data = coordinator
    entities = []

    try:
        await async_setup_entry(hass, entry, entities.extend)

        device_names = {
            entity.device_info["name"]
            for entity in entities
            if entity.device_info is not None
        }
        assert "System disk sda" in device_names
        assert "DISK sdb" in device_names
        assert "RAID md0" in device_names
        assert "VOLUME vg0-lv0" in device_names
    finally:
        await coordinator.async_shutdown()
