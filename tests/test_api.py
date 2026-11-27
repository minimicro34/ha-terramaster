"""Tests for the TerraMaster API parser."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import asyncssh

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
smart=sda|SMART Health Status: OK
smart=sdb|SMART overall-health self-assessment test result: PASSED
smart=sdb|  5 Reallocated_Sector_Ct   0x0033   200 200 140 Pre-fail Always - 2
smart=sdb| 12 Power_Cycle_Count       0x0032   100 100 000 Old_age Always - 430
smart=sdb|194 Temperature_Celsius     0x0022   104 100 000 Old_age Always - 39
smart=sdb|199 UDMA_CRC_Error_Count    0x0032   200 200 000 Old_age Always - 0
smart=sdb|241 Total_LBAs_Written      0x0032   100 100 000 Old_age Always - 12345678
smart=sdb|242 Total_LBAs_Read         0x0032   100 100 000 Old_age Always - 23456789
mdstat=md0 : active raid1 sdb4[0] sdc4[1]
mdstat=      971336704 blocks super 1.2 [2/2] [UU]
raid=md0|raid1|clean|0|idle|none
lsblk=NAME="md0" SIZE="994648784896"
filesystem=/dev/mapper/vg0-lv0|btrfs|971333632|444025736|524035576|/mnt/md0
filesystem=/dev/mapper/vg0-lv0|btrfs|971333632|444025736|524035576|/home
network=eth0|up|1000|1000000|500000
share=public|/mnt/md0/public|/dev/mapper/vg0-lv0|public|0|1|smb,nfs
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
    assert first.disks[0].smart_status == "ok"
    assert first.disks[0].temperature is None
    assert first.disks[0].power_on_hours is None
    assert first.disks[0].reallocated_sectors is None
    assert first.disks[1].is_system is False
    assert first.disks[1].temperature == 39.0
    assert first.disks[1].reallocated_sectors == 2
    assert first.disks[1].power_cycle_count == 430
    assert first.disks[1].udma_crc_errors == 0
    assert first.disks[0].total_read is None
    assert first.disks[0].total_written is None
    assert first.disks[1].total_read == 23456789 * 512
    assert first.disks[1].total_written == 12345678 * 512
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
    assert first.shares[0].protocols == ("smb", "nfs")
    assert first.services[0].name == "ssh"
    assert first.services[0].ports == (9222,)
    assert first.services[1].enabled is True
    assert first.services[1].ports == (23,)
    assert first.services[2].ports == (161,)


def test_parse_system_raids() -> None:
    """TerraMaster system RAID metadata is normalized using block metadata."""
    data = _client()._parse_output(  # noqa: SLF001
        """\
hostname=tnas
mdstat=md8 : active raid1 sdb3[0] sdc3[1]
mdstat=      2000000 blocks [24/2] [UU______________________]
raid=md8|raid1|clean|22|idle|none
lsblk=NAME="md8" SIZE="2050000000" FSTYPE="swap" MOUNTPOINT=""
mdstat=md9 : active raid1 sdb2[0] sdc2[1]
mdstat=      3000000 blocks [24/2] [UU______________________]
raid=md9|raid1|clean|22|idle|none
lsblk=NAME="md9" SIZE="3070000000" FSTYPE="ext4" MOUNTPOINT="/"
"""
    )

    md8, md9 = data.raids
    assert md8.is_system is True
    assert md8.system_type == "system_swap"
    assert md8.filesystem == "swap"
    assert md8.degraded_devices == 0
    assert md8.expected_devices == 24
    assert md8.active_devices == 2
    assert md8.members == ("sdb3", "sdc3")
    assert md9.is_system is True
    assert md9.system_type == "tos_system"
    assert md9.filesystem == "ext4"
    assert md9.mountpoint == "/"
    assert md9.degraded_devices == 0
    assert md9.members == ("sdb2", "sdc2")


def test_parse_missing_values() -> None:
    """Missing optional system files do not fail an update."""
    data = _client()._parse_output("hostname=tnas\n")  # noqa: SLF001

    assert data.hostname == "tnas"
    assert data.model is None
    assert data.cpu_usage is None
    assert data.disk_usage is None


async def test_privileged_metrics_prefer_direct_run() -> None:
    """TOS 7: privileged data is collected directly, without sudo."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        return_value=SimpleNamespace(
            exit_status=0,
            stdout=(
                "model=F4-425\n"
                "tos_version=7.0.12-345\n"
                "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
                "share=public|/mnt/md0/public|/dev/mapper/vg0-lv0|public|0|1|smb\n"
            ),
            stderr="",
        )
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "tos_version=7.0.12-345" in output
    assert "smart=sdb" in output
    command = connection.run.await_args.args[0]
    assert not command.startswith("sudo")
    assert connection.run.await_args.kwargs["input"] is None
    assert client._privileged_modes == {"smart": "direct", "share": "direct"}  # noqa: SLF001


async def test_privileged_metrics_fall_back_to_sudo() -> None:
    """TOS 4: without direct access the collection falls back to sudo."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(exit_status=0, stdout="model=F2-210\n", stderr=""),
            SimpleNamespace(
                exit_status=0,
                stdout=(
                    "model=F2-210\n"
                    "tos_version=4.2.44-294\n"
                    "smart=sdb|SMART overall-health self-assessment "
                    "test result: PASSED\n"
                    "share=public|/mnt/md0/public|/dev/mapper/vg0-lv0"
                    "|public|0|1|smb\n"
                ),
                stderr="",
            ),
        ]
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "tos_version=4.2.44-294" in output
    assert "smart=sdb" in output
    command = connection.run.await_args.args[0]
    assert command.startswith("sudo -S")
    assert "password" not in command
    assert connection.run.await_args.kwargs["input"] == "password\n"
    assert client._privileged_modes == {"smart": "sudo", "share": "sudo"}  # noqa: SLF001
    # The version-only output of the direct run is preserved.
    assert "model=F2-210" in output


async def test_privileged_metrics_partial_collection() -> None:
    """SMART via direct run and shares via sudo are merged."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(
                exit_status=0,
                stdout=(
                    "smart=sdb|SMART overall-health self-assessment "
                    "test result: PASSED\n"
                ),
                stderr="",
            ),
            SimpleNamespace(
                exit_status=0,
                stdout="share=public|/mnt/md0/public|/dev/mapper/vg0-lv0"
                "|public|0|1|smb\n",
                stderr="",
            ),
        ]
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "smart=sdb" in output
    assert "share=public" in output
    assert client._privileged_modes == {"smart": "direct", "share": "sudo"}  # noqa: SLF001

    # A subsequent poll runs each kind through its working mode only.
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(
                exit_status=0,
                stdout="smart=sdb|SMART overall-health self-assessment "
                "test result: PASSED\n",
                stderr="",
            ),
            SimpleNamespace(
                exit_status=0,
                stdout="share=public|/mnt/md0/public|/dev/mapper/vg0-lv0"
                "|public|0|1|smb\n",
                stderr="",
            ),
        ]
    )
    output = await client._async_collect_optional_data(connection)  # noqa: SLF001
    assert "smart=sdb" in output
    assert "share=public" in output
    commands = [call.args[0] for call in connection.run.await_args_list]
    assert not commands[0].startswith("sudo")
    assert commands[1].startswith("sudo -S")
    assert connection.run.await_count == 2


async def test_privileged_metrics_version_only_output_kept() -> None:
    """A run yielding only the TOS version still contributes it."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(
                exit_status=0, stdout="tos_version=4.2.44-294\n", stderr=""
            ),
            SimpleNamespace(exit_status=1, stdout="", stderr="denied"),
        ]
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert output.strip() == "tos_version=4.2.44-294"
    assert client._privileged_modes == {  # noqa: SLF001
        "smart": "unavailable",
        "share": "unavailable",
    }


async def test_privileged_metrics_root_runs_direct_only() -> None:
    """The root user never wraps the optional command in sudo."""
    client = TerraMasterApiClient("nas.local", 9222, "root", "password")
    connection = Mock()
    connection.run = AsyncMock(
        return_value=SimpleNamespace(
            exit_status=0,
            stdout=(
                "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
                "share=public|/mnt/md0/public|/dev/mapper/vg0-lv0|public|0|1|smb\n"
            ),
            stderr="",
        )
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "smart=sdb" in output
    assert connection.run.await_count == 1
    command = connection.run.await_args.args[0]
    assert not command.startswith("sudo")
    assert connection.run.await_args.kwargs["input"] is None


async def test_privileged_metrics_transient_failure_retried() -> None:
    """A transient SSH failure does not disable optional collection."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(side_effect=asyncssh.Error(255, "connection lost"))

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert output == ""
    assert client._privileged_modes == {"smart": None, "share": None}  # noqa: SLF001

    connection.run = AsyncMock(
        return_value=SimpleNamespace(
            exit_status=0,
            stdout=(
                "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
                "share=public|/mnt/md0/public|/dev/mapper/vg0-lv0|public|0|1|smb\n"
            ),
            stderr="",
        )
    )
    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert "smart=sdb" in output
    assert client._privileged_modes == {"smart": "direct", "share": "direct"}  # noqa: SLF001


async def test_privileged_metrics_unavailable() -> None:
    """Both direct and sudo failures disable optional collection."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        return_value=SimpleNamespace(exit_status=1, stdout="", stderr="denied")
    )

    output = await client._async_collect_optional_data(connection)  # noqa: SLF001

    assert output == ""
    assert client._privileged_modes == {  # noqa: SLF001
        "smart": "unavailable",
        "share": "unavailable",
    }
    # A subsequent poll does not retry.
    output = await client._async_collect_optional_data(connection)  # noqa: SLF001
    assert output == ""
    assert connection.run.await_count == 2


def test_parse_sata_lba_counters_require_known_names() -> None:
    """SATA attributes 241/242 are used only with known LBA semantics."""
    data = _client()._parse_output(  # noqa: SLF001
        "physical_disk=sdb|VendorX SSD|SN1|running|1953525168\n"
        "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
        "smart=sdb|241 Host_Writes_32MiB 0x0032 100 100 000 Old_age Always - 5000\n"
        "smart=sdb|242 Total_LBAs_Read 0x0032 100 100 000 Old_age Always - 23456789\n"
        "physical_disk=sdc|VendorY SSD|SN2|running|1953525168\n"
        "smart=sdc|SMART overall-health self-assessment test result: PASSED\n"
        "smart=sdc|241 Lifetime_Writes_GiB 0x0032 100 100 000 Old_age Always - 7000\n"
        "smart=sdc|242 Lifetime_Reads_GiB 0x0032 100 100 000 Old_age Always - 9000\n"
    )

    sdb, sdc = data.disks
    # 241 with unknown units must not be treated as 512-byte LBAs.
    assert sdb.total_written is None
    # 242 with the known "Total_LBAs_Read" name is converted.
    assert sdb.total_read == 23456789 * 512
    # Neither counter of the second disk has known LBA semantics.
    assert sdc.total_read is None
    assert sdc.total_written is None


def test_parse_nvme_disk() -> None:
    """NVMe SMART metrics are parsed from smartctl text output."""
    data = _client()._parse_output(  # noqa: SLF001
        "physical_disk=nvme0n1|KINGSTON SNV2S1000G|ABCD1234|live|1953525168\n"
        "smart=nvme0n1|SMART overall-health self-assessment test result: PASSED\n"
        "smart=nvme0n1|Temperature:                        38 Celsius\n"
        "smart=nvme0n1|Power On Hours:                     1,234\n"
        "smart=nvme0n1|Power Cycles:                       56\n"
        "smart=nvme0n1|Data Units Read:                    10,000 [5.12 GB]\n"
        "smart=nvme0n1|Data Units Written:                 20,000 [10.2 GB]\n"
    )

    (disk,) = data.disks
    assert disk.name == "nvme0n1"
    assert disk.model == "KINGSTON SNV2S1000G"
    assert disk.serial == "ABCD1234"
    assert disk.smart_status == "passed"
    assert disk.temperature == 38.0
    assert disk.power_on_hours == 1234
    assert disk.power_cycle_count == 56
    assert disk.total_read == 10000 * 512_000
    assert disk.total_written == 20000 * 512_000


async def test_tos4_partial_scsi_and_missing_model() -> None:
    """A permissive SCSI response must not hide a SATA permission failure."""
    client = _client()
    connection = Mock()
    basic = (
        "model=\ntos_version=4.2.41\n"
        "physical_disk=sdb|WDC WD10EFRX-68J||running|1953525168\n"
    )
    direct = (
        "smart_permission_denied=sdb\n"
        "smart=sdb|SMART Health Status: OK\n"
        "smart=sdb|Current Drive Temperature:     0 C\n"
        "smart=sdb|Drive Trip Temperature:        0 C\n"
        "share=public|/mnt/md0/public|/dev/md0|public|0|1|smb\n"
    )
    sudo = (
        "model=F2-210\n"
        "smart=sdb|SMART overall-health self-assessment test result: PASSED\n"
        "smart=sdb|  9 Power_On_Hours 0x0032 001 001 000 Old_age Always - 96002\n"
        "smart=sdb|194 Temperature_Celsius 0x0022 120 096 000 Old_age Always - 23\n"
    )
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(exit_status=0, stdout=direct, stderr=""),
            SimpleNamespace(exit_status=0, stdout=sudo, stderr=""),
        ]
    )
    output = await client._async_collect_optional_data(  # noqa: SLF001
        connection, basic_output=basic
    )
    data = client._parse_output(basic + output)  # noqa: SLF001
    assert data.model == "F2-210"
    (disk,) = data.disks
    assert disk.temperature == 23
    assert disk.power_on_hours == 96002
    assert disk.total_read is None
    assert disk.total_written is None
    assert connection.run.await_count == 2
    assert connection.run.await_args.args[0].startswith("sudo -S")
    assert client._privileged_modes["smart"] == "sudo"  # noqa: SLF001
    assert client._privileged_modes["model"] == "sudo"  # noqa: SLF001


async def test_missing_model_triggers_sudo_even_with_smart_and_shares() -> None:
    """Model collection is independent of SMART and shares."""
    client = _client()
    connection = Mock()
    connection.run = AsyncMock(
        side_effect=[
            SimpleNamespace(
                exit_status=0,
                stdout=(
                    "smart=sdb|SMART Health Status: OK\n"
                    "share=public|/mnt/md0/public|/dev/md0|public|0|1|smb\n"
                ),
                stderr="",
            ),
            SimpleNamespace(exit_status=0, stdout="model=F2-210\n", stderr=""),
        ]
    )
    output = await client._async_collect_optional_data(  # noqa: SLF001
        connection, basic_output="model=\n"
    )
    assert "model=F2-210" in output
    assert connection.run.await_count == 2
    assert client._privileged_modes["smart"] == "direct"  # noqa: SLF001
