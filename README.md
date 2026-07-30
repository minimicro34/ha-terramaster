# TerraMaster TOS for Home Assistant

A local-polling Home Assistant custom integration for TerraMaster NAS devices running
TOS 4. It connects over SSH with `asyncssh`; the default TerraMaster SSH port is
**9222**.

## Sensors

- Model and TOS version
- Uptime
- CPU usage
- Memory usage
- System temperature
- Aggregate disk usage (each physical/block device is counted once)

Model, version and temperature depend on the files exposed by a particular TOS build.
When TOS does not expose a metric, its entity remains unavailable without preventing
other sensors from updating. CPU usage becomes available after the second refresh,
because it is calculated from two `/proc/stat` samples.

## Installation with HACS

1. In HACS, open **Integrations**, choose **Custom repositories**, and add this
   repository as an **Integration**.
2. Download **TerraMaster TOS** and restart Home Assistant.
3. In Home Assistant, open **Settings → Devices & services → Add integration** and
   select **TerraMaster TOS**.

For a manual installation, copy `custom_components/terramaster` into Home Assistant's
`custom_components` directory and restart Home Assistant.

## TerraMaster preparation

Enable SSH in the TOS control panel. Create or choose the least-privileged account
which can read `/proc`, `/sys/class/thermal`, the TOS version/model files and `df`.
The integration does not require `sudo` and does not execute write operations.

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

The integration targets modern Home Assistant releases and Python 3.13. Run the
repository through `ruff`, `pytest`, `hassfest`, and HACS validation before publishing
a release.

## License

MIT
