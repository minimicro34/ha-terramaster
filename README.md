# TerraMaster TOS for Home Assistant

[![GitHub release](https://img.shields.io/github/v/release/minimicro34/ha-terramaster)](https://github.com/minimicro34/ha-terramaster/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/minimicro34/ha-terramaster)](LICENSE)

A local-polling Home Assistant custom integration for TerraMaster NAS devices running
TOS 4. It connects over SSH with `asyncssh`; the default TerraMaster SSH port is
**9222**.

## Features

- Local SSH polling on the TerraMaster default port `9222`
- Home Assistant config and reauthentication flows
- SSH host-key pinning
- Dynamic NAS, RAID, physical disk and volume discovery
- HACS compatible
- Coordinator-based polling
- Redacted diagnostics

## Sensors

- Commercial NAS model, hardware platform, TOS version, Linux distribution and
  kernel version
- Uptime in days and last TOS restart timestamp
- Processor model, aggregate CPU usage and dynamic per-core usage
- Total, available and percentage memory usage
- System temperature
- Aggregate disk usage (each physical/block device is counted once)
- RAID level, state, degraded disks and reconstruction progress
- Physical disk model, capacity, state and optional SMART health
- System boot USB and internal TOS RAID health, clearly marked as system storage
- Per-disk SMART health, temperature, power-on days, power/start/load cycles,
  reallocated or pending sectors, spin retries and UDMA CRC errors when permitted
- Per-volume capacity, used space, available space and usage
- Per-interface link state, negotiated speed, transferred data in GB and live traffic
  rates in Mbit/s
- TOS shared folders as entities on the main NAS device, with path, backing device,
  type, visibility and recycle-bin details
- SSH, Telnet and SNMP runtime status with listening protocol and port attributes

The commercial model is read with TOS's `getmodel` utility; the hardware platform is
reported separately. TOS 4 version detection includes `/usr/www/version`; the Linux
distribution comes from `os-release` or `openwrt_release`, and the kernel version from
`uname -r`. Temperature still depends on the sensors exposed by a particular TOS
build.
When TOS does not expose a metric, its entity remains unavailable without preventing
other sensors from updating. CPU usage becomes available after the second refresh,
because aggregate and per-core usage are calculated from two `/proc/stat` samples.

## Installation with HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/minimicro34/ha-terramaster` with category
   **Integration**.
3. Install **TerraMaster TOS** and restart Home Assistant.
4. In Home Assistant, open **Settings → Devices & services → Add integration** and
   select **TerraMaster TOS**.

For a manual installation, copy `custom_components/terramaster` into Home Assistant's
`custom_components` directory and restart Home Assistant.

## TerraMaster preparation

Enable SSH in the TOS control panel and use the primary TOS administrator account. On
TOS 4.2.12 and newer, TerraMaster uses the same password for SSH and `sudo`. The
integration runs one privileged, read-only collection block for the TOS version and
`smartctl -H -A -d sat`, the shared-folder database and listening service ports; it
does not execute write operations. The password is sent to `sudo -S` through standard
input and is never embedded in the remote command or written to logs. A failed sudo
authentication is not retried until the integration is reloaded, avoiding TOS's
temporary lockout after repeated failures.

If the account cannot use `sudo`, the NAS, RAID, volume and unprivileged system
sensors continue to work; the TOS-version, SMART, shared-folder and listening-service
details remain unavailable.

The first successful setup stores the NAS public SSH host key. All later connections
verify that key. If TOS is reinstalled or the key legitimately changes, start the
integration's reauthentication flow and verify that the change is expected.

## Troubleshooting

Enable debug logging:

```yaml
logger:
  logs:
    custom_components.terramaster: debug
```

Download diagnostics from the integration page when reporting an issue. Credentials,
host address, SSH host key, shared-folder names and shared-folder paths are redacted.

## Development

The integration targets Home Assistant 2026.7 or newer and Python 3.14. Run the
repository through `ruff`, `pytest`, `hassfest`, and HACS validation before publishing
a release.

Pull requests run Ruff, mypy, pytest, Hassfest and HACS validation automatically.

The SSH implementation is split into `api/client.py`, `api/exceptions.py` and
`api/parsers.py`. Storage models live in `models.py`; Home Assistant platforms only
consume coordinator snapshots and do not execute remote commands directly.

## License

MIT
