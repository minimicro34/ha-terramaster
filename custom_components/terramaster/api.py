"""SSH API client for TerraMaster TOS 4."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncssh

from .models import TerraMasterData

_LOGGER = logging.getLogger(__name__)


class TerraMasterError(Exception):
    """Base TerraMaster API exception."""


class TerraMasterConnectionError(TerraMasterError):
    """Raised when the SSH connection fails."""


class TerraMasterAuthenticationError(TerraMasterError):
    """Raised when SSH authentication fails."""


class TerraMasterHostKeyError(TerraMasterError):
    """Raised when the server host key has changed."""


class TerraMasterCommandError(TerraMasterError):
    """Raised when the remote collection command fails."""


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
        self._lock = asyncio.Lock()

    async def async_test_connection(self) -> str:
        """Connect and return the server public key for pinning."""
        connection = await self._async_connect(trust_on_first_use=True)
        try:
            key = connection.get_server_host_key()
            return key.export_public_key().decode().strip()
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
                    result.stderr.strip() or f"Command exited with {result.exit_status}"
                )

            return self._parse_output(result.stdout)

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
            else:
                values[key] = value

        cpu_usage = self._calculate_cpu(values.get("cpu"))
        memory_usage = _percentage(
            _as_int(values.get("mem_total"), default=0)
            - _as_int(values.get("mem_available"), default=0),
            _as_int(values.get("mem_total"), default=0),
        )
        disk_usage = self._calculate_disk_usage(disks)
        temperature = _as_float(values.get("temperature"))
        if temperature is not None and temperature > 1000:
            temperature /= 1000

        return TerraMasterData(
            hostname=values.get("hostname") or self._host,
            model=values.get("model") or None,
            tos_version=values.get("tos_version") or None,
            uptime=_as_int(values.get("uptime")),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            temperature=temperature,
            disk_usage=disk_usage,
        )

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
        return _percentage(used, total)


def _as_int(value: str | None, *, default: int | None = None) -> int | None:
    try:
        return int(value) if value else default
    except ValueError:
        return default


def _as_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _percentage(used: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, used * 100 / total)), 1)
