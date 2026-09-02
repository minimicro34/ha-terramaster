# TerraMaster TOS for Home Assistant

Local monitoring of TerraMaster NAS devices from Home Assistant over SSH.

[![Release](https://img.shields.io/github/v/release/minimicro34/ha-terramaster)](https://github.com/minimicro34/ha-terramaster/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://www.hacs.xyz/)
[![Validate](https://github.com/minimicro34/ha-terramaster/actions/workflows/validate.yml/badge.svg)](https://github.com/minimicro34/ha-terramaster/actions/workflows/validate.yml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-%E2%98%95-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/minimicro34)
[![License](https://img.shields.io/github/license/minimicro34/ha-terramaster)](LICENSE)

## Features

- NAS model, TOS version, Linux distribution and kernel
- Uptime, last restart, CPU, CPU cores, memory and temperature
- Physical disks and SMART health information, including system-disk fallback where supported
- RAID arrays, members, degradation, purpose and synchronization status/progress
- Volumes, capacity and usage
- Network interfaces, counters and real-time throughput
- SSH, Telnet and SNMP service detection
- Shared-folder discovery from the TOS database
- SMB, NFS and AFP protocol detection
- Secure HTML pages for all shares or one selected share
- Direct access to the shares page from the main NAS device in Home Assistant
- Navigation between the NAS device, shares index and individual share pages
- English and French translations

The integration polls locally and does not require a cloud account.

## Requirements

- Home Assistant with HACS
- SSH enabled on the TerraMaster NAS
- A TOS account allowed to connect through SSH
- Administrator access through `sudo` for optional SMART, service and shared-folder details

The integration uses read-only commands. The configured password is used for SSH and, when available, read-only `sudo` collection.

## Installation

### HACS custom repository

1. Open **HACS**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/minimicro34/ha-terramaster`.
4. Select **Integration** as the category.
5. Install **TerraMaster TOS**.
6. Restart Home Assistant.

### Manual installation

Copy:

```text
custom_components/terramaster
```

to:

```text
/config/custom_components/terramaster
```

and restart Home Assistant.

## Configuration

In Home Assistant:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **TerraMaster TOS**.
4. Enter the NAS address, SSH port, username and password.

The default SSH port is `9222`, but the configured TOS port can be used.

The SSH host key is recorded during the first connection and checked on later connections.

## Shared folders

The main NAS device provides a **Visit** link that opens the secure TerraMaster shares page directly.

The main **Shared folders** sensor displays the number of detected shares. Its attributes contain:

- the share names;
- all detected protocols;
- `open_shares`, a secure link to the general shared-folder page.

Each individual shared-folder diagnostic entity keeps the detailed information:

- path, type, visibility and recycle-bin state;
- volume, RAID and filesystem;
- capacity, used space and available space in decimal GB;
- usage percentage;
- SMB, NFS and AFP URLs;
- `open_share`, a secure link to the HTML page for that share.

The shares index and individual share pages provide navigation back to the main NAS device. Individual share pages also provide a direct link back to the shares index.

Passwords are never included in connection URLs. SMB and AFP URLs can include the configured username so the operating system can request or reuse the password.

## Storage and SMART

Physical disks expose the storage and SMART information supported by the device.

Normal ATA disks use SAT SMART collection first. Devices that do not expose usable SMART health through SAT can fall back to permissive SCSI health collection. This is used, for example, for the TerraMaster USB system disk when supported by `smartctl`.

System disks intentionally expose only relevant storage information and SMART health; unsupported ATA counters and invalid values such as a reported `0 °C` temperature are not exposed.

## RAID arrays

RAID devices expose their level, capacity, state, members and degraded-disk count.

Synchronization is represented by two separate entities:

- **Synchronization action** reports states such as `idle`, `resync` or `recover`.
- **Synchronization progress** reports the percentage while an operation is active and `None` / `Aucune` while idle.

TerraMaster system RAID arrays are identified as TOS system or system swap where this can be determined from filesystem and mount information. TerraMaster's system-array metadata may contain 24 logical RAID slots even when only the installed physical members are expected; this metadata is normalized so it does not produce a misleading degraded-disk count in the primary Home Assistant UI.

## Devices and entities

The NAS is the main Home Assistant device. Physical disks, RAID arrays, volumes and network interfaces are represented as child devices where appropriate.

Some metrics require administrator access. When optional privileged collection is unavailable, the basic NAS metrics continue working.

## Tested hardware

Confirmed during development:

- TerraMaster F2-210
- TOS 4.2.41

Other TOS 4, TOS 5 and TOS 6 devices may work, but should be treated as unverified until reported by users.

## Troubleshooting

### Shared folders are missing

Verify that the configured SSH user can run:

```sh
sudo sqlite3 -separator '|' /etc/base/nasdb   'SELECT foldername,mntpath,device,type,hidden,recycle FROM share;'
```

### SMART data is missing

Verify that `smartctl` is installed on the NAS and that the configured account can execute it through `sudo`.

SMART support depends on the disk and bridge presented by the NAS. The integration prefers SAT for normal ATA disks and only uses the permissive SCSI fallback when SAT does not provide a usable SMART health result.

### Authentication or host-key error

Remove and re-add the integration only after confirming that the NAS address and SSH host key change are expected.

## Privacy and security

- Communication stays on the local network.
- No cloud service is used.
- The SSH server host key is pinned.
- Shared-folder HTML pages use a random token stored in the Home Assistant config entry.
- Passwords are not exposed in entity attributes or URLs.

## Development checks

```sh
pytest
mypy custom_components/terramaster
ruff check .
```

## Release history

### 1.1.0

Improved SMART handling for TerraMaster system disks, expanded RAID information and system-array handling, and improved shared-folder navigation with direct access from the main NAS device.

### 1.0.0

First stable release with system, SMART, RAID, volume, network, services and shared-folder monitoring.

See [CHANGELOG.md](CHANGELOG.md) for the complete release history, including beta releases.

## Contributing

Contributions are welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

For significant changes, please open an issue before submitting a pull request.

## Support

If you find TerraMaster TOS for Home Assistant useful and would like to support
its development, you can buy me a coffee.

<p align="center">
  <a href="https://buymeacoffee.com/minimicro34">
    <img
      src="https://github.com/appcraftstudio/buymeacoffee/raw/master/Images/snapshot-bmc-button.png"
      alt="Buy Me a Coffee"
      width="300"
    />
  </a>
</p>

Your support helps me dedicate more time to improving the integration, adding new
features, testing additional TerraMaster TOS configurations and fixing issues.

Bug reports, feature suggestions, contributions and GitHub stars are also
greatly appreciated.

Please use GitHub Issues for bug reports and feature requests.

When reporting an issue, please include whenever possible:

- TerraMaster NAS model;
- TOS version;
- TerraMaster integration version;
- Home Assistant version;
- a clear description of the problem;
- relevant Home Assistant logs;
- Home Assistant diagnostics.

For SSH or data-collection problems, please also include:

- the authentication method used (password or SSH key);
- whether the SSH connection works outside Home Assistant;
- which sensor or data category is affected;
- relevant command errors, with sensitive information redacted.

Never include passwords, SSH private keys, authentication credentials or other
sensitive NAS information.

## License

Copyright (c) 2026 minimicro34

This project is licensed under the [GNU General Public License v3.0 or later](LICENSE).
