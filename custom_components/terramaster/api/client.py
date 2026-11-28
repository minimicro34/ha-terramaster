"""SSH API client for TerraMaster TOS 4/5/6/7."""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from typing import Any, NamedTuple

import asyncssh

from ..models import (
    TerraMasterCpuCore,
    TerraMasterData,
    TerraMasterDisk,
    TerraMasterNetwork,
    TerraMasterRaid,
    TerraMasterService,
    TerraMasterShare,
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
    NVME_METRIC,
    SMART_ATTRIBUTE,
    as_float,
    as_int,
    percentage,
    sync_progress,
)

_LOGGER = logging.getLogger(__name__)

# Kinds of privileged data from the optional collection, tracked
# independently: SMART needs device access, shares need nasdb access,
# and a single mode (direct or sudo) may provide only one of them.
_PRIVILEGED_KINDS = ("smart", "share")

# SATA attributes 241/242 are vendor-specific: only counters explicitly
# named "Total_LBAs_Written/Read" are known to count 512-byte LBAs.
# Other firmware reuses these attribute IDs for different units.
_SATA_LBA_COUNTER_NAMES = {241: "total_lbas_written", 242: "total_lbas_read"}


class _OptionalRun(NamedTuple):
    """Result of a single optional collection attempt."""

    output: str | None
    transient: bool


def _sata_lba_count(
    attributes: dict[int, int], names: dict[int, str], attribute_id: int
) -> int | None:
    """Return a raw SATA LBA counter only when its semantics are known."""
    if names.get(attribute_id, "").casefold() != _SATA_LBA_COUNTER_NAMES[attribute_id]:
        return None
    return attributes.get(attribute_id)


def _smart_total_bytes(sata_lbas: int | None, nvme_units: int | None) -> int | None:
    """Convert SMART lifetime counters to bytes.

    SATA attributes 241/242 count 512-byte LBAs (accepted only when the
    counter name confirms LBA semantics, see `_sata_lba_count`); NVMe
    "Data Units Read/Written" count units of 512,000 bytes.
    """
    if sata_lbas is not None:
        return sata_lbas * 512
    if nvme_units is not None:
        return nvme_units * 512_000
    return None


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
model=''
if command -v getmodel >/dev/null 2>&1; then
    model=$(getmodel 2>/dev/null)
elif [ -x /sbin/getmodel ]; then
    model=$(/sbin/getmodel 2>/dev/null)
fi
[ "$model" = "---" ] && model=''
if [ -z "$model" ]; then
    model_candidate=$(first_file /sys/class/dmi/id/product_name \
        /etc/terramaster/model)
    case "$model_candidate" in *-*) model=$model_candidate ;; esac
fi
printf 'model=%s\n' "$model"
platform=$(first_file /etc/model /proc/device-tree/model \
    /tmp/sysinfo/model /tmp/sysinfo/board_name)
printf 'platform=%s\n' "$platform"
tos_version=''
for file in /usr/www/version /etc/version /etc/TOS_VERSION /etc/tos_version \
    /etc/tos-version /etc/tos-release /etc/TOS_RELEASE \
    /etc/tnas_version /etc/terramaster/version /etc/base/*version* \
    /etc/base/*release* /usr/local/etc/version /usr/www/*version* \
    /usr/www/include/*version* /usr/www/inc/*version* \
    /etc/tos/version /etc/tos/release /etc/tos/*version* /etc/tos/*release* \
    /etc/tos/config/login_title.conf \
    /etc/TOS/version /etc/terramaster/release /etc/terramaster/TOS_VERSION \
    /etc/conf.d/*version* /etc/issue; do
    [ -r "$file" ] || continue
    # Prefer a line mentioning TOS so that, e.g., an Ubuntu version string
    # in /etc/issue is not picked over the TOS version on TOS 7.
    tos_version=$(awk '
        /TOS/ && match($0, /[0-9]+\.[0-9]+\.[0-9]+([-._][0-9]+)?/) \
        {print substr($0, RSTART, RLENGTH); printed=1; exit}
        !found && match($0, /[0-9]+\.[0-9]+\.[0-9]+([-._][0-9]+)?/) \
        {candidate=substr($0, RSTART, RLENGTH); found=1}
        END {if (!printed && found) print candidate}' "$file" 2>/dev/null)
    [ -n "$tos_version" ] && break
done
printf 'tos_version=%s\n' "$tos_version"
linux_distribution=''
if [ -r /etc/os-release ]; then
    linux_distribution=$(awk -F= '/^PRETTY_NAME=/ {
        sub(/^[^=]*=/, ""); gsub(/"/, ""); print; exit
    }' /etc/os-release)
fi
if [ -z "$linux_distribution" ] && [ -r /etc/openwrt_release ]; then
    linux_distribution=$(awk -F= '/^DISTRIB_DESCRIPTION=/ {
        sub(/^[^=]*=/, ""); gsub(/\047/, ""); print; exit
    }' /etc/openwrt_release)
fi
printf 'linux_distribution=%s\n' "$linux_distribution"
printf 'kernel_version='; uname -r 2>/dev/null
printf 'uptime='; cut -d. -f1 /proc/uptime 2>/dev/null
printf 'boot_time='; awk '/^btime / {print $2}' /proc/stat
printf 'mem_total='; awk '/^MemTotal:/ {print $2}' /proc/meminfo
printf 'mem_available='; awk '/^MemAvailable:/ {print $2}' /proc/meminfo
if ! grep -q '^MemAvailable:' /proc/meminfo; then
    printf 'mem_available='
    awk '/^MemFree:|^Buffers:|^Cached:/ {sum += $2} END {print sum}' \
        /proc/meminfo
fi
cpu_model=$(awk -F: \
    '/^(model name|Processor|Hardware)[[:space:]]*:/ {
        sub(/^[[:space:]]+/, "", $2); print $2; exit
    }' /proc/cpuinfo 2>/dev/null)
if [ -z "$cpu_model" ]; then
    cpu_implementer=$(awk -F: '/^CPU implementer/ {
        gsub(/[[:space:]]/, "", $2); print tolower($2); exit
    }' /proc/cpuinfo 2>/dev/null)
    cpu_part=$(awk -F: '/^CPU part/ {
        gsub(/[[:space:]]/, "", $2); print tolower($2); exit
    }' /proc/cpuinfo 2>/dev/null)
    case "$cpu_implementer:$cpu_part" in
        0x41:0xd03) cpu_model='ARM Cortex-A53' ;;
        0x41:0xd04) cpu_model='ARM Cortex-A35' ;;
        0x41:0xd05) cpu_model='ARM Cortex-A55' ;;
        0x41:0xd07) cpu_model='ARM Cortex-A57' ;;
        0x41:0xd08) cpu_model='ARM Cortex-A72' ;;
        0x41:0xd09) cpu_model='ARM Cortex-A73' ;;
        0x41:0xd0a) cpu_model='ARM Cortex-A75' ;;
        0x41:0xd0b) cpu_model='ARM Cortex-A76' ;;
        0x41:0xd41) cpu_model='ARM Cortex-A78' ;;
    esac
fi
[ -z "$cpu_model" ] && cpu_model=$(uname -m 2>/dev/null)
printf 'cpu_model=%s\n' "$cpu_model"
printf 'cpu='; awk '/^cpu / {print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat
awk '/^cpu[0-9]+ / {
    printf "cpu_core=%s", $1
    for (field = 2; field <= 9; field++) printf " %s", $field
    print ""
}' /proc/stat
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
done
for disk_path in /sys/block/nvme[0-9]*n[0-9]*; do
    [ -d "$disk_path" ] || continue
    disk_name=${disk_path##*/}
    disk_model=$(cat "$disk_path/device/model" 2>/dev/null)
    disk_serial=$(cat "$disk_path/device/serial" 2>/dev/null)
    disk_state=$(cat "$disk_path/device/state" 2>/dev/null)
    disk_sectors=$(cat "$disk_path/size" 2>/dev/null)
    printf 'physical_disk=%s|%s|%s|%s|%s\n' \
        "$disk_name" "$disk_model" "$disk_serial" "$disk_state" "$disk_sectors"
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


_OPTIONAL_COMMAND = r"""
model=''
if command -v getmodel >/dev/null 2>&1; then
    model=$(getmodel 2>/dev/null)
elif [ -x /sbin/getmodel ]; then
    model=$(/sbin/getmodel 2>/dev/null)
fi
[ "$model" = "---" ] && model=''
[ -n "$model" ] && printf 'model=%s\n' "$model"

tos_version=''
for file in /usr/www/version /etc/version /etc/TOS_VERSION /etc/tos_version \
    /etc/tos-version /etc/tos-release /etc/TOS_RELEASE \
    /etc/tnas_version /etc/terramaster/version /etc/base/*version* \
    /etc/base/*release* /usr/local/etc/version /usr/www/*version* \
    /usr/www/include/*version* /usr/www/inc/*version* \
    /etc/tos/version /etc/tos/release /etc/tos/*version* /etc/tos/*release* \
    /etc/tos/config/login_title.conf \
    /etc/TOS/version /etc/terramaster/release /etc/terramaster/TOS_VERSION \
    /etc/conf.d/*version* /etc/issue; do
    [ -r "$file" ] || continue
    # Prefer a line mentioning TOS so that, e.g., an Ubuntu version string
    # in /etc/issue is not picked over the TOS version on TOS 7.
    tos_version=$(awk '
        /TOS/ && match($0, /[0-9]+\.[0-9]+\.[0-9]+([-._][0-9]+)?/) \
        {print substr($0, RSTART, RLENGTH); printed=1; exit}
        !found && match($0, /[0-9]+\.[0-9]+\.[0-9]+([-._][0-9]+)?/) \
        {candidate=substr($0, RSTART, RLENGTH); found=1}
        END {if (!printed && found) print candidate}' "$file" 2>/dev/null)
    [ -n "$tos_version" ] && break
done
[ -n "$tos_version" ] && printf 'tos_version=%s\n' "$tos_version"

if command -v smartctl >/dev/null 2>&1; then
    for disk_path in /sys/block/sd*; do
        [ -d "$disk_path" ] || continue
        disk_name=${disk_path##*/}
        smart_output=$(smartctl -H -A -d sat "/dev/$disk_name" 2>&1)
        if printf '%s\n' "$smart_output" | grep -qi \
            -e "Operation not permitted" -e "Permission denied"; then
            printf 'smart_permission_denied=%s\n' "$disk_name"
        fi
        if ! printf '%s\n' "$smart_output" | grep -q \
            -e 'SMART overall-health' -e 'SMART Health Status:'; then
            smart_output=$(smartctl -H -A -T permissive -d scsi "/dev/$disk_name" 2>&1)
        fi
        if printf '%s\n' "$smart_output" | grep -q \
            -e 'SMART overall-health' -e 'SMART Health Status:'; then
            printf '%s\n' "$smart_output" | while IFS= read -r smart_line; do
                [ -n "$smart_line" ] && printf 'smart=%s|%s\n' \
                    "$disk_name" "$smart_line"
            done
        fi
    done
    for ns_path in /sys/block/nvme[0-9]*n[0-9]*; do
        [ -d "$ns_path" ] || continue
        ns_name=${ns_path##*/}
        ctrl_name=${ns_name%n[0-9]*}
        # Query each NVMe controller once, through its first namespace.
        [ "$ns_name" = "${ctrl_name}n1" ] || continue
        smart_output=$(smartctl -H -A "/dev/$ctrl_name" 2>&1)
        if printf '%s\n' "$smart_output" | grep -q \
            -e 'SMART overall-health' -e 'SMART Health Status:'; then
            printf '%s\n' "$smart_output" | while IFS= read -r smart_line; do
                [ -n "$smart_line" ] && printf 'smart=%s|%s\n' \
                    "$ns_name" "$smart_line"
            done
        fi
    done
fi

ini_has_section() {
    awk -v target="$2" '
        /^[[:space:]]*\[/ {
            section=$0
            sub(/^[[:space:]]*\[/, "", section)
            sub(/\][[:space:]]*.*$/, "", section)
            if (tolower(section) == tolower(target)) found=1
        }
        END {exit found ? 0 : 1}
    ' "$1" 2>/dev/null
}

nfs_exports_path() {
    awk -v target="$2" '
        /^[[:space:]]*#/ || NF == 0 {next}
        {
            path=$1
            gsub(/\\040/, " ", path)
            if (path == target) found=1
        }
        END {exit found ? 0 : 1}
    ' "$1" 2>/dev/null
}

nfs_server_running() {
    for process in rpc.mountd rpc.nfsd mountd nfsd; do
        pidof "$process" >/dev/null 2>&1 && return 0
    done
    [ -r /proc/fs/nfsd/versions ] && \
        grep -Eq '\+[234](\\.|[[:space:]]|$)' /proc/fs/nfsd/versions 2>/dev/null
}

nfs_share_exported() {
    target=$1
    for exports_file in /etc/exports /var/lib/nfs/etab /etc/exports.d/*; do
        [ -r "$exports_file" ] || continue
        nfs_exports_path "$exports_file" "$target" && return 0
    done
    if command -v exportfs >/dev/null 2>&1; then
        exportfs -v 2>/dev/null | awk -v target="$target" '
            /^[[:space:]]*\/[^[:space:]]*/ {
                path=$1
                gsub(/\\040/, " ", path)
                if (path == target) found=1
            }
            END {exit found ? 0 : 1}
        '
        return $?
    fi
    return 1
}

if command -v sqlite3 >/dev/null 2>&1 && [ -r /etc/base/nasdb ]; then
    sqlite3 -separator '|' /etc/base/nasdb \
        'SELECT foldername,mntpath,device,type,hidden,recycle FROM share;' \
        2>/dev/null | while IFS='|' read -r share_name share_path \
            share_device share_type share_hidden share_recycle; do
        share_protocols=''
        if pidof smbd >/dev/null 2>&1 && [ -r /etc/samba/smb.conf ] && \
            ini_has_section /etc/samba/smb.conf "$share_name"; then
            share_protocols='smb'
        fi
        if nfs_server_running && nfs_share_exported "$share_path"; then
            [ -n "$share_protocols" ] && share_protocols="$share_protocols,nfs" || \
                share_protocols='nfs'
        fi
        if pidof netatalk >/dev/null 2>&1 && [ -r /etc/afp.conf ] && \
            ini_has_section /etc/afp.conf "$share_name"; then
            [ -n "$share_protocols" ] && share_protocols="$share_protocols,afp" || \
                share_protocols='afp'
        fi
        printf 'share=%s|%s|%s|%s|%s|%s|%s\n' "$share_name" "$share_path" \
            "$share_device" "$share_type" "$share_hidden" "$share_recycle" \
            "$share_protocols"
    done
fi

if command -v netstat >/dev/null 2>&1; then
    printf 'listeners_available=1\n'
    netstat -lntup 2>/dev/null | awk \
        'NR > 2 && ($1 ~ /^tcp/ || $1 ~ /^udp/) \
        {print "listener=" $1 "|" $4 "|" $NF}'
fi
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
        self._previous_cpu_cores: dict[str, tuple[int, int]] = {}
        self._previous_network: dict[str, tuple[float, int, int]] = {}
        self._privileged_modes: dict[str, str | None] = {
            kind: None for kind in _PRIVILEGED_KINDS
        }
        self._clock = time.monotonic
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
            return _to_text(key.export_public_key()).strip()
        finally:
            connection.close()
            await connection.wait_closed()

    async def async_get_data(self) -> TerraMasterData:
        """Fetch a system data snapshot."""
        async with self._lock:
            connection = await self._async_connect()
            try:
                result = await connection.run(_COLLECT_COMMAND, check=False, timeout=30)
                if result.exit_status != 0:
                    raise TerraMasterCommandError(
                        _to_text(result.stderr).strip()
                        or f"Command exited with {result.exit_status}"
                    )
                output = _to_text(result.stdout)
                optional_output = await self._async_collect_optional_data(
                    connection, basic_output=output
                )
            except (TimeoutError, asyncssh.Error, OSError) as err:
                raise TerraMasterConnectionError(str(err)) from err
            finally:
                connection.close()
                await connection.wait_closed()

            return self._parse_output("\n".join((output, optional_output)))

    async def _async_collect_optional_data(
        self, connection: asyncssh.SSHClientConnection, *, basic_output: str = ""
    ) -> str:
        """Collect read-only version, SMART and shared-folder data.

        A direct run is tried first: on newer TOS versions the shell user
        can read SMART data directly, while ``sudo`` actually restricts
        device access. Older TOS versions fall back to ``sudo``. SMART
        and shared-folder data may be reachable through different modes,
        so each kind is tracked independently and partial outputs are
        merged. The working mode per kind is cached for the lifetime of
        the client; transient SSH failures are not latched and are
        retried on the next poll.
        """
        if basic_output and not self._has_marker(basic_output, "model"):
            self._privileged_modes.setdefault("model", None)
        pending = {
            kind
            for kind, mode in self._privileged_modes.items()
            if mode != "unavailable"
        }
        if not pending:
            return ""

        if self._username == "root":
            modes: tuple[str, ...] = ("direct",)
        else:
            preferred = [
                mode
                for kind in self._privileged_modes
                if kind in pending
                and (mode := self._privileged_modes[kind]) is not None
            ]
            modes = tuple(dict.fromkeys((*preferred, "direct", "sudo")))

        outputs: list[str] = []
        transient_failure = False
        for mode in modes:
            if not pending:
                break
            run = await self._async_run_optional(
                connection, use_sudo=mode == "sudo"
            )
            if run.output is None:
                transient_failure = transient_failure or run.transient
                continue
            # Even a version-only output is kept: the TOS version may be
            # readable exclusively through this command on some devices.
            outputs.append(run.output)
            for kind in tuple(pending):
                if not self._has_marker(run.output, kind):
                    continue
                if kind == "smart" and any(
                    line.startswith("smart_permission_denied=")
                    for line in run.output.splitlines()
                ):
                    continue
                if self._privileged_modes[kind] not in (None, mode):
                    _LOGGER.debug(
                        "TerraMaster %s metrics mode switched to %s", kind, mode
                    )
                self._privileged_modes[kind] = mode
                pending.discard(kind)

        if pending and not transient_failure:
            for kind in pending:
                if any(self._has_marker(output, kind) for output in outputs):
                    self._privileged_modes[kind] = None
                else:
                    self._privileged_modes[kind] = "unavailable"
            _LOGGER.debug(
                "Optional TerraMaster metrics are unavailable "
                "both directly and through sudo: %s",
                ", ".join(sorted(pending)),
            )
        return "\n".join(outputs)

    async def _async_run_optional(
        self, connection: asyncssh.SSHClientConnection, *, use_sudo: bool
    ) -> _OptionalRun:
        """Run the optional collection command, optionally through sudo."""
        if use_sudo:
            command = f"sudo -S -p '' sh -c {shlex.quote(_OPTIONAL_COMMAND)}"
            run_input: str | None = f"{self._password}\n"
        else:
            command = _OPTIONAL_COMMAND
            run_input = None
        try:
            result = await connection.run(
                command,
                input=run_input,
                check=False,
                timeout=30,
            )
        except (TimeoutError, asyncssh.Error, OSError) as err:
            _LOGGER.debug(
                "Optional TerraMaster metrics failed (%s): %s",
                "sudo" if use_sudo else "direct",
                err,
            )
            return _OptionalRun(output=None, transient=True)
        if result.exit_status != 0:
            _LOGGER.debug(
                "Optional TerraMaster metrics (%s) exited with %s: %s",
                "sudo" if use_sudo else "direct",
                result.exit_status,
                _to_text(result.stderr).strip(),
            )
            return _OptionalRun(output=None, transient=False)
        return _OptionalRun(output=_to_text(result.stdout), transient=False)

    @staticmethod
    def _has_marker(output: str, kind: str) -> bool:
        """Return whether the output contains data of the given kind."""
        prefix = f"{kind}="
        return any(
            line.startswith(prefix) and line[len(prefix):].strip()
            for line in output.splitlines()
        )

    async def _async_connect(
        self, *, trust_on_first_use: bool = False
    ) -> asyncssh.SSHClientConnection:
        known_hosts: Any = None
        try:
            if not trust_on_first_use and self._host_key:
                known_hosts = (
                    [asyncssh.import_public_key(self._host_key)],
                    [],
                    [],
                    [],
                    [],
                    [],
                    [],
                )
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
        except (asyncssh.HostKeyNotVerifiable, asyncssh.KeyImportError) as err:
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
        cpu_core_rows: list[str] = []
        share_rows: list[str] = []
        listener_rows: list[str] = []
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
            elif key == "cpu_core":
                cpu_core_rows.append(value)
            elif key == "share":
                share_rows.append(value)
            elif key == "listener":
                listener_rows.append(value)
            else:
                values[key] = value

        cpu_usage = self._calculate_cpu(values.get("cpu"))
        memory_total_kib = as_int(values.get("mem_total"), default=0) or 0
        memory_available_kib = as_int(values.get("mem_available"), default=0) or 0
        memory_usage = percentage(
            memory_total_kib - memory_available_kib, memory_total_kib
        )
        disk_usage = self._calculate_disk_usage(disks)
        temperature = as_float(values.get("temperature"))
        if temperature is not None and temperature > 1000:
            temperature /= 1000

        return TerraMasterData(
            hostname=values.get("hostname") or self._host,
            model=values.get("model") or None,
            platform=values.get("platform") or None,
            tos_version=values.get("tos_version") or None,
            linux_distribution=values.get("linux_distribution") or None,
            kernel_version=values.get("kernel_version") or None,
            uptime=as_int(values.get("uptime")),
            boot_time=as_int(values.get("boot_time")),
            cpu_model=values.get("cpu_model") or None,
            cpu_usage=cpu_usage,
            memory_total=memory_total_kib * 1024 if memory_total_kib else None,
            memory_available=(
                memory_available_kib * 1024 if memory_available_kib else None
            ),
            memory_usage=memory_usage,
            temperature=temperature,
            disk_usage=disk_usage,
            disks=self._parse_physical_disks(physical_disks, smart_lines),
            raids=self._parse_raids(mdstat_lines, raid_details, lsblk_rows),
            volumes=self._parse_volumes(filesystems),
            networks=self._parse_networks(network_rows),
            cpu_cores=self._parse_cpu_cores(cpu_core_rows),
            shares=self._parse_shares(share_rows),
            services=self._parse_services(
                listener_rows, values.get("listeners_available") == "1"
            ),
        )

    def _parse_networks(self, rows: list[str]) -> tuple[TerraMasterNetwork, ...]:
        now = self._clock()
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
                    receive_rate = round(
                        (received - previous[1]) * 8 / elapsed / 1_000_000, 3
                    )
                    transmit_rate = round(
                        (sent - previous[2]) * 8 / elapsed / 1_000_000, 3
                    )
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

    def _parse_cpu_cores(self, rows: list[str]) -> tuple[TerraMasterCpuCore, ...]:
        cores: list[TerraMasterCpuCore] = []
        active_names: set[str] = set()
        for row in rows:
            name, separator, counters = row.partition(" ")
            if not separator or not name.startswith("cpu"):
                continue
            active_names.add(name)
            previous = self._previous_cpu_cores.get(name)
            current, usage = _cpu_sample(counters, previous)
            if current is None:
                continue
            self._previous_cpu_cores[name] = current
            cores.append(TerraMasterCpuCore(name=name, usage=usage))
        self._previous_cpu_cores = {
            name: sample
            for name, sample in self._previous_cpu_cores.items()
            if name in active_names
        }
        return tuple(cores)

    @staticmethod
    def _parse_shares(rows: list[str]) -> tuple[TerraMasterShare, ...]:
        shares: list[TerraMasterShare] = []
        for row in rows:
            parts = row.split("|", 6)
            if len(parts) not in (6, 7) or not parts[0]:
                continue
            name, path, device, share_type, hidden, recycle_bin = parts[:6]
            protocols = parts[6].split(",") if len(parts) == 7 else []
            shares.append(
                TerraMasterShare(
                    name=name,
                    path=path,
                    device=device,
                    share_type=share_type,
                    hidden=hidden == "1",
                    recycle_bin=recycle_bin == "1",
                    protocols=tuple(
                        protocol
                        for protocol in ("smb", "nfs", "afp")
                        if protocol in protocols
                    ),
                )
            )
        return tuple(sorted(shares, key=lambda share: share.name.casefold()))

    def _parse_services(
        self, rows: list[str], listeners_available: bool
    ) -> tuple[TerraMasterService, ...]:
        detected: dict[str, tuple[set[int], set[str]]] = {}
        process_names = {"ssh": "sshd", "telnet": "telnetd", "snmp": "snmpd"}
        for row in rows:
            parts = row.split("|", 2)
            if len(parts) != 3:
                continue
            protocol, address, process = parts
            port = as_int(address.rpartition(":")[2])
            if port is None:
                continue
            for service_name, process_name in process_names.items():
                if process_name in process.lower():
                    ports, protocols = detected.setdefault(service_name, (set(), set()))
                    ports.add(port)
                    protocols.add(protocol.rstrip("6"))

        ssh_ports, ssh_protocols = detected.setdefault("ssh", (set(), set()))
        ssh_ports.add(self._port)
        ssh_protocols.add("tcp")
        return tuple(
            TerraMasterService(
                name=name,
                enabled=(name in detected)
                if listeners_available or name == "ssh"
                else None,
                ports=tuple(sorted(detected.get(name, (set(), set()))[0])),
                protocols=tuple(sorted(detected.get(name, (set(), set()))[1])),
            )
            for name in ("ssh", "telnet", "snmp")
        )

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
            attribute_names: dict[int, str] = {}
            health: str | None = None
            nvme_temperature: float | None = None
            nvme_power_on_hours: int | None = None
            nvme_power_cycles: int | None = None
            nvme_data_units_read: int | None = None
            nvme_data_units_written: int | None = None
            for line in smart.get(name, []):
                lower = line.lower()
                if "test result:" in lower or "smart health status:" in lower:
                    health = line.rsplit(":", 1)[-1].strip().lower()
                match = SMART_ATTRIBUTE.match(line)
                if match:
                    attribute_id = int(match.group(1))
                    attribute_names[attribute_id] = match.group(2)
                    attributes[attribute_id] = int(match.group(3))
                    continue
                nvme_match = NVME_METRIC.search(line)
                if nvme_match is None:
                    continue
                number = nvme_match.group(1).replace(",", "")
                if lower.startswith("temperature:"):
                    nvme_temperature = float(number)
                elif lower.startswith("power on hours:"):
                    nvme_power_on_hours = int(float(number))
                elif lower.startswith("power cycles:"):
                    nvme_power_cycles = int(float(number))
                elif lower.startswith("data units read:"):
                    nvme_data_units_read = int(float(number))
                elif lower.startswith("data units written:"):
                    nvme_data_units_written = int(float(number))
            result.append(
                TerraMasterDisk(
                    name=name,
                    model=model.strip() or None,
                    serial=serial or None,
                    size=size_bytes,
                    state=state or None,
                    is_system=is_system,
                    smart_status=health,
                    temperature=(
                        float(attributes[194])
                        if 194 in attributes
                        else nvme_temperature
                    ),
                    power_on_hours=attributes.get(9, nvme_power_on_hours),
                    power_cycle_count=attributes.get(12, nvme_power_cycles),
                    start_stop_count=attributes.get(4),
                    load_cycle_count=attributes.get(193),
                    spin_retry_count=attributes.get(10),
                    reallocated_sectors=attributes.get(5),
                    reallocated_events=attributes.get(196),
                    pending_sectors=attributes.get(197),
                    offline_uncorrectable=attributes.get(198),
                    udma_crc_errors=attributes.get(199),
                    total_read=_smart_total_bytes(
                        _sata_lba_count(attributes, attribute_names, 242),
                        nvme_data_units_read,
                    ),
                    total_written=_smart_total_bytes(
                        _sata_lba_count(attributes, attribute_names, 241),
                        nvme_data_units_written,
                    ),
                )
            )
        return tuple(result)

    @staticmethod
    def _parse_raids(
        lines: list[str], details: dict[str, list[str]], lsblk: list[dict[str, str]]
    ) -> tuple[TerraMasterRaid, ...]:
        block_rows = {row.get("NAME"): row for row in lsblk if row.get("NAME")}
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
            block = block_rows.get(name, {})
            filesystem = block.get("FSTYPE") or None
            mountpoint = block.get("MOUNTPOINT") or None
            size = as_int(block.get("SIZE"))
            is_system = (
                name in {"md8", "md9"}
                or filesystem == "swap"
                or mountpoint == "/"
            )
            system_type: str | None = None
            if is_system:
                if filesystem == "swap" or name == "md8":
                    system_type = "system_swap"
                elif mountpoint == "/" or name == "md9":
                    system_type = "tos_system"
            if is_system and active:
                degraded = 0
            raids.append(
                TerraMasterRaid(
                    name=name,
                    level=detail[0] or level,
                    state=detail[1],
                    size=size,
                    members=tuple(MD_MEMBER.findall(member_text)),
                    expected_devices=expected,
                    active_devices=active,
                    degraded_devices=degraded,
                    sync_action=detail[3],
                    sync_progress=sync_progress(detail[4]),
                    is_system=is_system,
                    filesystem=filesystem,
                    mountpoint=mountpoint,
                    system_type=system_type,
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
        current, usage = _cpu_sample(value, self._previous_cpu)
        if current is not None:
            self._previous_cpu = current
        return usage

    @staticmethod
    def _calculate_disk_usage(
        disks: list[tuple[str, int, int, str]],
    ) -> float | None:
        unique: dict[str, tuple[int, int]] = {}
        for device, total, used, mountpoint in disks:
            if total > 0 and not mountpoint.startswith(("/boot", "/var/", "/usr/")):
                unique.setdefault(device, (total, used))
        total = sum(item[0] for item in unique.values())
        used = sum(item[1] for item in unique.values())
        return percentage(used, total)


def _cpu_sample(
    value: str, previous: tuple[int, int] | None
) -> tuple[tuple[int, int] | None, float | None]:
    """Parse CPU counters and calculate utilization since the previous sample."""
    try:
        counters = [int(part) for part in value.split()]
    except ValueError:
        return None, None
    if len(counters) < 4:
        return None, None
    idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
    total = sum(counters)
    current = (total, idle)
    if previous is None:
        return current, None
    total_delta = total - previous[0]
    idle_delta = idle - previous[1]
    if total_delta <= 0:
        return current, None
    usage = round(
        max(0.0, min(100.0, 100 * (total_delta - idle_delta) / total_delta)), 1
    )
    return current, usage


def _to_text(value: bytes | str | None) -> str:
    """Normalize optional AsyncSSH process output to text."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
