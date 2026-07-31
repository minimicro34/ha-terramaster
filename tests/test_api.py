"""Tests for the TerraMaster API parser."""

from custom_components.terramaster.api import TerraMasterApiClient

SAMPLE = """\
hostname=tnas
model=F4-220
tos_version=4.2.41
uptime=86400
boot_time=1785350000
mem_total=1000
mem_available=250
cpu=100 0 50 850 0 0 0 0
temperature=42500
disk=/dev/md0 1000 500 /Volume1
disk=/dev/md0 1000 500 /mnt/bind
disk=/dev/md1 2000 500 /Volume2
physical_disk=sda|USB DISK 2.0||running|245760
physical_disk=sdb|WDC WD10EFRX-68J||running|1953525168
smart=sdb|SMART overall-health self-assessment test result: PASSED
smart=sdb|  5 Reallocated_Sector_Ct   0x0033   200 200 140 Pre-fail Always - 2
smart=sdb| 12 Power_Cycle_Count       0x0032   100 100 000 Old_age Always - 430
smart=sdb|194 Temperature_Celsius     0x0022   104 100 000 Old_age Always - 39
smart=sdb|199 UDMA_CRC_Error_Count    0x0032   200 200 000 Old_age Always - 0
mdstat=md0 : active raid1 sdb4[0] sdc4[1]
mdstat=      971336704 blocks super 1.2 [2/2] [UU]
raid=md0|raid1|clean|0|idle|none
lsblk=NAME="md0" SIZE="994648784896"
filesystem=/dev/mapper/vg0-lv0|btrfs|971333632|444025736|524035576|/mnt/md0
filesystem=/dev/mapper/vg0-lv0|btrfs|971333632|444025736|524035576|/home
"""


def _client() -> TerraMasterApiClient:
    return TerraMasterApiClient("nas.local", 9222, "user", "password")


def test_parse_output() -> None:
    """A TOS snapshot is parsed and normalized."""
    client = _client()
    first = client._parse_output(SAMPLE)  # noqa: SLF001
    second = client._parse_output(  # noqa: SLF001
        SAMPLE.replace("cpu=100 0 50 850", "cpu=150 0 100 950")
    )

    assert first.hostname == "tnas"
    assert first.model == "F4-220"
    assert first.tos_version == "4.2.41"
    assert first.uptime == 86400
    assert first.boot_time == 1785350000
    assert first.memory_usage == 75.0
    assert first.temperature == 42.5
    assert first.disk_usage == 33.3
    assert first.cpu_usage is None
    assert second.cpu_usage == 50.0
    assert [disk.name for disk in first.disks] == ["sda", "sdb"]
    assert first.disks[0].is_system is True
    assert first.disks[1].is_system is False
    assert first.disks[1].temperature == 39.0
    assert first.disks[1].reallocated_sectors == 2
    assert first.disks[1].power_cycle_count == 430
    assert first.disks[1].udma_crc_errors == 0
    assert first.raids[0].state == "clean"
    assert first.raids[0].members == ("sdb4", "sdc4")
    assert len(first.volumes) == 1


def test_parse_missing_values() -> None:
    """Missing optional system files do not fail an update."""
    data = _client()._parse_output("hostname=tnas\n")  # noqa: SLF001

    assert data.hostname == "tnas"
    assert data.model is None
    assert data.cpu_usage is None
    assert data.disk_usage is None
