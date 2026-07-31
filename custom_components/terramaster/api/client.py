"""SSH API client for TerraMaster TOS 4."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from typing import Any, cast

import asyncssh

from ..models import (
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterNetwork,
    TerraMasterRaid,
    TerraMasterVolume,
)
from .exceptions import (
    TerraMasterAuthenticationError,
    TerraMasterCommandError,
    TerraMasterConnectionError,
    TerraMasterHostKeyError,
)
from .parsers import (
    MD_HEADER,
    MD_MEMBER,
    MD_STATUS,
    SMART_ATTRIBUTE,
    as_float,
    as_int,
    percentage,
    sync_progress,
)

_LOGGER = logging.getLogger(__name__)


_COLLECT_COMMAND = r"""
set -u
first_file() {
    for file in "$@"; do
        if [ -r "$file" ]; then
            head -n 1 "$file" 2>/dev/null
            return
        fi
    done
}
printf 'hostname='; hostname 2>/dev/null || uname -n
model=$(first_file /etc/model /etc/terramaster/model /proc/device-tree/model)
printf 'model=%s\n' "$model"
tos_version=$(first_file /etc/version /etc/TOS_VERSION /etc/terramaster/version)
if [ -z "$tos_version" ] && [ -r /etc/os-release ]; then
    tos_version=$(awk -F= '/^VERSION_ID=/ {gsub(/"/, "", $2); print $2}' \
        /etc/os-release)
fi
printf 'tos_version=%s\n' "$tos_version"
printf 'uptime='; cut -d. -f1 /proc/uptime 2>/dev/null
printf 'boot_time='; awk '/^btime / {print $2}' /proc/stat
printf 'mem_total='; awk '/^MemTotal:/ {print $2}' /proc/meminfo
printf 'mem_available='; awk '/^MemAvailable:/ {print $2}' /proc/meminfo
if ! grep -q '^MemAvailable:' /proc/meminfo; then
    printf 'mem_available='
    awk '/^MemFree:|^Buffers:|^Cached:/ {sum += $2} END {print sum}' \
        /proc/meminfo
fi
printf 'cpu='; awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat
temperature=''
for file in /sys/class/thermal/thermal_zone*/temp \
    /sys/class/hwmon/hwmon*/temp*_input; do
    if [ -r "$file" ]; then
        value=$(head -n 1 "$file" 2>/dev/null)
        [ -n "$value" ] && { temperature=$value; break; }
    fi
done
printf 'temperature=%s\n' "$temperature"
df -Pk 2>/dev/null | awk \
    'NR > 1 && $1 ~ "^/dev/" {print "disk=" $1 " " $2 " " $3 " " $6}'
lsblk -b -P -o NAME,KNAME,TYPE,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT 2>/dev/null | \
    while IFS= read -r line; do printf 'lsblk=%s\n' "$line"; done
df -PT -k 2>/dev/null | awk \
    'NR > 1 {print "filesystem=" $1 "|" $2 "|" $3 "|" $4 "|" $5 "|" $7}'
while IFS= read -r line; do printf 'mdstat=%s\n' "$line"; done < /proc/mdstat
for md_path in /sys/block/md*; do
    [ -d "$md_path/md" ] || continue
    md_name=${md_path##*/}
    level=$(cat "$md_path/md/level" 2>/dev/null)
    state=$(cat "$md_path/md/array_state" 2>/dev/null)
    degraded=$(cat "$md_path/md/degraded" 2>/dev/null)
    action=$(cat "$md_path/md/sync_action" 2>/dev/null)
    completed=$(cat "$md_path/md/sync_completed" 2>/dev/null)
    printf 'raid=%s|%s|%s|%s|%s|%s\n' \
        "$md_name" "$level" "$state" "$degraded" "$action" "$completed"
done
for disk_path in /sys/block/sd*; do
    disk_name=${disk_path##*/}
    disk_model=$(cat "$disk_path/device/model" 2>/dev/null)
    disk_serial=$(cat "$disk_path/device/serial" 2>/dev/null)
    disk_state=$(cat "$disk_path/device/state" 2>/dev/null)
    disk_sectors=$(cat "$disk_path/size" 2>/dev/null)
    printf 'physical_disk=%s|%s|%s|%s|%s\n' \
        "$disk_name" "$disk_model" "$disk_serial" "$disk_state" "$disk_sectors"
    if command -v smartctl >/dev/null 2>&1; then
        smart_output=$(smartctl -H -A -d sat "/dev/$disk_name" 2>/dev/null)
        if ! printf '%s\n' "$smart_output" | \
            grep -q 'START OF READ SMART DATA' && \
            command -v sudo >/dev/null 2>&1; then
            smart_output=$(sudo -n smartctl -H -A -d sat \
                "/dev/$disk_name" 2>/dev/null)
        fi
        printf '%s\n' "$smart_output" | while IFS= read -r smart_line; do
            [ -n "$smart_line" ] && printf 'smart=%s|%s\n' \
                "$disk_name" "$smart_line"
        done
    fi
done
for net_path in /sys/class/net/*; do
    net_name=${net_path##*/}
    case "$net_name" in lo|docker*|veth*|br-*|tun*|tap*) continue ;; esac
    net_state=$(cat "$net_path/operstate" 2>/dev/null)
    net_speed=$(cat "$net_path/speed" 2>/dev/null)
    net_rx=$(cat "$net_path/statistics/rx_bytes" 2>/dev/null)
    net_tx=$(cat "$net_path/statistics/tx_bytes" 2>/dev/null)
    printf 'network=%s|%s|%s|%s|%s\n' \
        "$net_name" "$net_state" "$net_speed" "$net_rx" "$net_tx"
done
""".strip()


class TerraMasterApiClient:
    """Read TerraMaster system data over SSH."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        host_key: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._host_key = host_key
        self._previous_cpu: tuple[int, int] | None = None
        self._previous_network: dict[str, tuple[float, int, int]] = {}
        self._lock = asyncio.Lock()

    async def async_test_connection(self) -> str:
        """Connect and return the server public key for pinning."""
        connection = await self._async_connect(trust_on_first_use=True)
        try:
            key = connection.get_server_host_key()
            if key is None:
                raise TerraMasterHostKeyError(
                    "The SSH server did not provide a host key"
                )
            return cast("bytes", key.export_public_key()).decode().strip()
        finally:
            connection.close()
            await connection.wait_closed()

    async def async_get_data(self) -> TerraMasterData:
        """Fetch a system data snapshot."""
        async with self._lock:
            connection = await self._async_connect()
            try:
                result = await connection.run(_COLLECT_COMMAND, check=False, timeout=30)
            except (TimeoutError, asyncssh.Error, OSError) as err:
                raise TerraMasterConnectionError(str(err)) from err
            finally:
                connection.close()
                await connection.wait_closed()

            if result.exit_status != 0:
                raise TerraMasterCommandError(
                    _to_text(result.stderr).strip()
                    or f"Command exited with {result.exit_status}"
                )

            return self._parse_output(_to_text(result.stdout))

    async def _async_connect(
        self, *, trust_on_first_use: bool = False
    ) -> asyncssh.SSHClientConnection:
        known_hosts: Any = None
        if not trust_on_first_use and self._host_key:
            known_hosts = f"[{self._host}]:{self._port} {self._host_key}\n".encode()

        try:
            return await asyncssh.connect(
                self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                known_hosts=known_hosts,
                client_keys=None,
                login_timeout=20,
                keepalive_interval=15,
                keepalive_count_max=2,
            )
        except asyncssh.PermissionDenied as err:
            raise TerraMasterAuthenticationError(str(err)) from err
        except asyncssh.HostKeyNotVerifiable as err:
            raise TerraMasterHostKeyError(str(err)) from err
        except (TimeoutError, asyncssh.Error, OSError) as err:
            raise TerraMasterConnectionError(str(err)) from err

    def _parse_output(self, output: str) -> TerraMasterData:
        values: dict[str, str] = {}
        disks: list[tuple[str, int, int, str]] = []
        lsblk_rows: list[dict[str, str]] = []
        filesystems: list[str] = []
        mdstat_lines: list[str] = []
        raid_details: dict[str, list[str]] = {}
        physical_disks: dict[str, list[str]] = {}
        smart_lines: dict[str, list[str]] = {}
        network_rows: list[str] = []
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if not separator:
                continue
            value = value.strip().strip("\x00")
            if key == "disk":
                parts = value.split(maxsplit=3)
                if len(parts) == 4:
                    try:
                        disks.append((parts[0], int(parts[1]), int(parts[2]), parts[3]))
                    except ValueError:
                        _LOGGER.debug("Ignoring invalid disk row: %s", value)
            elif key == "lsblk":
                try:
                    lsblk_rows.append(
                        dict(item.split("=", 1) for item in shlex.split(value))
                    )
                except ValueError:
                    _LOGGER.debug("Ignoring invalid lsblk row: %s", value)
            elif key == "filesystem":
                filesystems.append(value)
            elif key == "mdstat":
                mdstat_lines.append(value)
            elif key == "raid":
                parts = value.split("|", 5)
                if len(parts) == 6:
                    raid_details[parts[0]] = parts[1:]
            elif key == "physical_disk":
                parts = value.split("|", 4)
                if len(parts) == 5:
                    physical_disks[parts[0]] = parts[1:]
            elif key == "smart":
                name, separator, line = value.partition("|")
                if separator:
                    smart_lines.setdefault(name, []).append(line)
            elif key == "network":
                network_rows.append(value)
            else:
                values[key] = value

        cpu_usage = self._calculate_cpu(values.get("cpu"))
        memory_total = as_int(values.get("mem_total"), default=0) or 0
        memory_available = as_int(values.get("mem_available"), default=0) or 0
        memory_usage = percentage(memory_total - memory_available, memory_total)
        disk_usage = self._calculate_disk_usage(disks)
        temperature = as_float(values.get("temperature"))
        if temperature is not None and temperature > 1000:
            temperature /= 1000

        return TerraMasterData(
            hostname=values.get("hostname") or self._host,
            model=values.get("model") or None,
            tos_version=values.get("tos_version") or None,
            uptime=as_int(values.get("uptime")),
            boot_time=as_int(values.get("boot_time")),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            temperature=temperature,
            disk_usage=disk_usage,
            disks=self._parse_physical_disks(physical_disks, smart_lines),
            raids=self._parse_raids(mdstat_lines, raid_details, lsblk_rows),
            volumes=self._parse_volumes(filesystems),
            networks=self._parse_networks(network_rows),
        )

    def _parse_networks(self, rows: list[str]) -> tuple[TerraMasterNetwork, ...]:
        now = time.monotonic()
        networks: list[TerraMasterNetwork] = []
        for row in rows:
            parts = row.split("|", 4)
            if len(parts) != 5:
                continue
            name, state, speed_text, received_text, sent_text = parts
            received = as_int(received_text)
            sent = as_int(sent_text)
            if received is None or sent is None:
                continue
            receive_rate: float | None = None
            transmit_rate: float | None = None
            if previous := self._previous_network.get(name):
                elapsed = now - previous[0]
                if elapsed > 0 and received >= previous[1] and sent >= previous[2]:
                    receive_rate = round((received - previous[1]) / elapsed, 1)
                    transmit_rate = round((sent - previous[2]) / elapsed, 1)
            self._previous_network[name] = (now, received, sent)
            networks.append(
                TerraMasterNetwork(
                    name=name,
                    state=state or None,
                    speed=as_int(speed_text),
                    received_bytes=received,
                    sent_bytes=sent,
                    receive_rate=receive_rate,
                    transmit_rate=transmit_rate,
                )
            )
        return tuple(networks)

    @staticmethod
    def _parse_physical_disks(
        rows: dict[str, list[str]], smart: dict[str, list[str]]
    ) -> tuple[TerraMasterDisk, ...]:
        result: list[TerraMasterDisk] = []
        for name, (model, serial, state, sectors) in sorted(rows.items()):
            size = as_int(sectors)
            if size is None:
                continue
            size_bytes = size * 512
            is_system = size_bytes < 10_000_000_000
            attributes: dict[int, int] = {}
            health: str | None = None
            for line in smart.get(name, []):
                if "test result:" in line:
                    health = line.rsplit(":", 1)[-1].strip().lower()
                match = SMART_ATTRIBUTE.match(line)
                if match:
                    attributes[int(match.group(1))] = int(match.group(2))
            result.append(
                TerraMasterDisk(
                    name=name,
                    model=model.strip() or None,
                    serial=serial or None,
                    size=size_bytes,
                    state=state or None,
                    is_system=is_system,
                    smart_status=health,
                    temperature=(float(attributes[194]) if 194 in attributes else None),
                    power_on_hours=attributes.get(9),
                    power_cycle_count=attributes.get(12),
                    start_stop_count=attributes.get(4),
                    load_cycle_count=attributes.get(193),
                    spin_retry_count=attributes.get(10),
                    reallocated_sectors=attributes.get(5),
                    reallocated_events=attributes.get(196),
                    pending_sectors=attributes.get(197),
                    offline_uncorrectable=attributes.get(198),
                    udma_crc_errors=attributes.get(199),
                )
            )
        return tuple(result)

    @staticmethod
    def _parse_raids(
        lines: list[str], details: dict[str, list[str]], lsblk: list[dict[str, str]]
    ) -> tuple[TerraMasterRaid, ...]:
        sizes = {row.get("NAME"): as_int(row.get("SIZE")) for row in lsblk}
        raids: list[TerraMasterRaid] = []
        for index, line in enumerate(lines):
            header = MD_HEADER.match(line)
            if not header:
                continue
            name, level, member_text = header.groups()
            status = MD_STATUS.search(
                lines[index + 1] if index + 1 < len(lines) else ""
            )
            expected = int(status.group(1)) if status else None
            active = int(status.group(2)) if status else None
            detail = details.get(name, [level, None, None, None, None])
            degraded = as_int(detail[2])
            # md8/md9 are intentionally sparse TOS system arrays.
            is_system = name in {"md8", "md9"}
            if is_system and active:
                degraded = 0
            raids.append(
                TerraMasterRaid(
                    name=name,
                    level=detail[0] or level,
                    state=detail[1],
                    size=sizes.get(name),
                    members=tuple(MD_MEMBER.findall(member_text)),
                    expected_devices=expected,
                    active_devices=active,
                    degraded_devices=degraded,
                    sync_action=detail[3],
                    sync_progress=sync_progress(detail[4]),
                    is_system=is_system,
                )
            )
        return tuple(raids)

    @staticmethod
    def _parse_volumes(lines: list[str]) -> tuple[TerraMasterVolume, ...]:
        volumes: dict[str, TerraMasterVolume] = {}
        for line in lines:
            parts = line.split("|", 5)
            if len(parts) != 6 or not parts[0].startswith("/dev/mapper/"):
                continue
            device, filesystem, total, used, available, mountpoint = parts
            total_kib, used_kib, available_kib = map(int, (total, used, available))
            volumes.setdefault(
                device,
                TerraMasterVolume(
                    name=device.rsplit("/", 1)[-1],
                    device=device,
                    filesystem=filesystem,
                    mountpoint=mountpoint,
                    size=total_kib * 1024,
                    used=used_kib * 1024,
                    available=available_kib * 1024,
                    usage=percentage(used_kib, total_kib) or 0,
                ),
            )
        return tuple(volumes.values())

    def _calculate_cpu(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            counters = [int(part) for part in value.split()]
        except ValueError:
            return None
        if len(counters) < 4:
            return None
        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
        total = sum(counters)
        previous, self._previous_cpu = self._previous_cpu, (total, idle)
        if previous is None:
            return None
        total_delta = total - previous[0]
        idle_delta = idle - previous[1]
        if total_delta <= 0:
            return None
        return round(
            max(0.0, min(100.0, 100 * (total_delta - idle_delta) / total_delta)), 1
        )

    @staticmethod
    def _calculate_disk_usage(
        disks: list[tuple[str, int, int, str]],
    ) -> float | None:
        # df may list bind mounts more than once. Count each block device once.
        unique: dict[str, tuple[int, int]] = {}
        for device, total, used, mountpoint in disks:
            if total > 0 and not mountpoint.startswith(("/boot", "/var/", "/usr/")):
                unique.setdefault(device, (total, used))
        total = sum(item[0] for item in unique.values())
        used = sum(item[1] for item in unique.values())
        return percentage(used, total)


def _to_text(value: bytes | str | None) -> str:
    """Normalize optional AsyncSSH process output to text."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
