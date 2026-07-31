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

- Model and TOS version
- Uptime and last TOS restart timestamp
- CPU usage
- Memory usage
- System temperature
- Aggregate disk usage (each physical/block device is counted once)
- RAID level, state, degraded disks and reconstruction progress
- Physical disk model, capacity, state and optional SMART health
- System boot USB and internal TOS RAID health, clearly marked as system storage
- Per-disk SMART health, temperature, power-on hours, power/start/load cycles,
  reallocated or pending sectors, spin retries and UDMA CRC errors when permitted
- Per-volume capacity, used space, available space and usage
- Per-interface link state, negotiated speed, transferred data and live traffic rates

Model, version and temperature depend on the files exposed by a particular TOS build.
When TOS does not expose a metric, its entity remains unavailable without preventing
other sensors from updating. CPU usage becomes available after the second refresh,
because it is calculated from two `/proc/stat` samples.

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

Enable SSH in the TOS control panel. Create or choose the least-privileged account
which can read `/proc`, `/sys/class/thermal`, the TOS version/model files and `df`.
The integration does not require `sudo` and does not execute write operations.

SMART data is optional. If TOS restricts `smartctl` to root, you can grant the SSH
account passwordless access to the read-only `smartctl -H -A -d sat` command. The
integration first tries direct access and then `sudo -n`; it never sends a sudo
password. Without this permission, the NAS, RAID and volume sensors continue to work
and only SMART-specific entities remain unavailable.

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
host address and the SSH host key are redacted.

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
