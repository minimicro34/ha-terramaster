"""Tests for the TerraMaster API parser."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from custom_components.terramaster.api import TerraMasterApiClient

SAMPLE = """\
hostname=tnas
model=F4-220
platform=Realtek_RTD1296
tos_version=4.2.41
linux_distribution=OpenWrt Chaos Calmer 15.05.1
kernel_version=4.4.18-g8bcbd8a-dirty
uptime=86400
boot_time=1785350000
mem_total=1000
mem_available=250
cpu_model=ARMv8 Processor rev 4
cpu=100 0 50 850 0 0 0 0
cpu_core=cpu0 50 0 25 425 0 0 0 0
cpu_core=cpu1 50 0 25 425 0 0 0 0
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
network=eth0|up|1000|1000000|500000
share=public|/mnt/md0/public|/dev/mapper/vg0-lv0|public|0|1
listeners_available=1
listener=tcp|0.0.0.0:9222|123/sshd
listener=tcp|0.0.0.0:23|456/telnetd
listener=udp|0.0.0.0:161|789/snmpd
"""


def _client() -> TerraMasterApiClient:
    return TerraMasterApiClient("nas.local", 9222, "user", "password")


def test_parse_output() -> None:
    """A TOS snapshot is parsed and normalized."""
    client = _client()
    samples = iter((100.0, 102.0))
    client._clock = lambda: next(samples)  # noqa: SLF001
    first = client._parse_output(SAMPLE)  # noqa: SLF001
    second = client._parse_output(  # noqa: SLF001
        SAMPLE.replace("cpu=100 0 50 850", "cpu=150 0 100 950")
        .replace("cpu_core=cpu0 50 0 25 425", "cpu_core=cpu0 75 0 50 475")
        .replace("cpu_core=cpu1 50 0 25 425", "cpu_core=cpu1 90 0 35 475")
        .replace(
            "network=eth0|up|1000|1000000|500000",
            "network=eth0|up|1000|2000000|1000000",
        )
    )

    assert first.hostname == "tnas"
    assert first.model == "F4-220"
    assert first.platform == "Realtek_RTD1296"
    assert first.tos_version == "4.2.41"
    assert first.linux_distribution == "OpenWrt Chaos Calmer 15.05.1"
    assert first.kernel_version == "4.4.18-g8bcbd8a-dirty"
    assert first.uptime == 86400
    assert first.boot_time == 1785350000
    assert first.cpu_model == "ARMv8 Processor rev 4"
    assert first.memory_total == 1024000
    assert first.memory_available == 256000
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
    assert first.networks[0].name == "eth0"
    assert first.networks[0].speed == 1000
    assert first.networks[0].receive_rate is None
    assert second.networks[0].receive_rate == 4.0
    assert second.networks[0].transmit_rate == 2.0
    assert [core.name for core in first.cpu_cores] == ["cpu0", "cpu1"]
    assert first.cpu_cores[0].usage is None
    assert second.cpu_cores[0].usage == 50.0
    assert first.shares[0].name == "public"
    assert first.shares[0].recycle_bin is True
    assert first.services[0].name == "ssh"
    assert first.services[0].ports == (9222,)
    assert first.services[1].enabled is True
    assert first.services[1].ports == (23,)
    assert first.services[2].ports == (161,)


def test_parse_missing_values() -> None:
    """Missing optional system files do not fail an update."""
    data = _client()._parse_output("hostname=tnas\n")  # noqa: SLF001

    assert data.hostname == "tnas"
    assert data.model is None
    assert data.cpu_usage is None
    assert data.disk_usage is None


async def test_privileged_metrics_use_password_on_stdin() -> None:
    """SMART and TOS version collection uses sudo without exposing the password."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        return_value=SimpleNamespace(
            exit_status=0,
            stdout=(
                "tos_version=4.2.44-294\n"
                "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
            ),
            stderr="",
        )
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "tos_version=4.2.44-294" in output
    assert "smart=sdb" in output
    command = connection.run.await_args.args[0]
    assert command.startswith("sudo -S")
    assert "password" not in command
    assert connection.run.await_args.kwargs["input"] == "password\n"
