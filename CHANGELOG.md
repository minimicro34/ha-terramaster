# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

---

## [1.1.5-beta1] - 2026-11-03

### Fixed
- Discover TerraMaster sensors through the Home Assistant entity registry, including translated entity IDs.
- Resolve dashboard metrics from stable entity unique IDs and scope discovery to one NAS.
- Support full-width cards in Home Assistant Sections dashboards.

### Tests
- Cover translated entity IDs, NAS isolation and Sections grid options.

## [1.1.4] - 2026-11-03

### Fixed
- Replace deprecated device registry lookup with the config-entry-scoped `async_get_device_by_identifier` API for compatibility with Home Assistant 2027.8.0 and later.

## [1.1.3] - 2026-11-03

### Added
- Bundle an experimental Lovelace NAS dashboard with CPU, memory, temperature, storage and system summary tiles.
- Add collapsible disk/SMART, RAID, volume, network and service detail sections that retain their expanded state on refresh.
- Add a shares button that requests a short-lived signed URL through `terramaster.get_share_link` without storing a permanent token in the card.
- Add JavaScript syntax checks and card tests for rendering, collapsible sections, HTML escaping and signed-link handling.
- Enforce a minimum of 80% Python test coverage in GitHub Actions and generate a coverage XML report.

### Changed
- Display the NAS model in the dashboard header when available.
- Document local virtual-environment setup and development checks.

### Fixed
- Avoid exposing a legacy persistent share-page URL through the NAS device configuration link.

## [1.1.2] - 2026-11-02

Security hardening and authenticated share-page access.

### Security
- Require Home Assistant authentication for shared-folder HTML views instead of permanent query-string tokens.
- Remove legacy shared-folder tokens from configuration entries and redact them from diagnostics.
- Remove persistent share-page URLs from entity attributes and NAS device links.

### Added
- Add the `terramaster.get_share_link` Home Assistant action, returning signed share-page paths valid for five minutes.
- Sign links back to the shared-folder index from individual share pages.

### Changed
- Document the new manual action workflow for securely accessing the share pages.
- Retain SMB, NFS, and AFP connection URLs on share sensors.

## [1.1.0] - 2026-09-02

Stable release of the changes tested in `1.1.0-beta1` and `1.1.0-beta2`.

### Added
- Added SMART health fallback for devices requiring permissive SCSI access.
- Added RAID member information.
- Added system RAID purpose information for TOS and swap arrays.
- Added direct access to the TerraMaster shares page from the main NAS device.
- Added navigation between individual share pages, the TerraMaster shares index, and the NAS device page in Home Assistant.
- Added automated tests covering SMART fallback, system disks, RAID details, synchronization display, and share navigation.

### Changed
- Keep SAT SMART collection as preferred mode for normal ATA disks and use permissive SCSI only as fallback.
- System disks expose only essential storage information and SMART health.
- RAID synchronization action and synchronization progress remain separate entities.
- Idle RAID synchronization progress is displayed as none/“Aucune” rather than unavailable.
- System RAID role is inferred from filesystem/mount information where available.
- RAID device naming/translations improved for system arrays.
- Share pages provide a direct “Back to NAS” / “Retour au NAS” link instead of returning to the Home Assistant root page.

### Fixed
- SMART health can be reported for the TerraMaster USB system disk without exposing bogus 0 °C temperature or unsupported ATA counters.
- TerraMaster system RAID metadata with 24 logical slots no longer implies 24 expected physical disks/degraded hardware in the primary UI.

## [1.1.0-beta2] - 2026-09-02

### Added
- Added direct access to the TerraMaster shares page from the main NAS device.
- Added navigation between individual share pages, the TerraMaster shares index, and the NAS device page in Home Assistant.

### Changed
- Share pages now provide a direct “Back to NAS” / “Retour au NAS” link instead of returning to the Home Assistant root page.

## [1.1.0-beta1] - 2026-09-02

### Added
- Added SMART health fallback for devices requiring permissive SCSI access.
- Added RAID member information.
- Added system RAID purpose information for TOS and swap arrays.
- Added navigation between individual share pages, the TerraMaster shares index, and Home Assistant.
- Added automated tests covering SMART fallback, system disks, RAID details, synchronization display, and share navigation.

### Changed
- Keep SAT SMART collection as preferred mode for normal ATA disks and use permissive SCSI only as fallback.
- System disks expose only essential storage information and SMART health.
- RAID synchronization action and synchronization progress remain separate entities.
- Idle RAID synchronization progress is displayed as none/“Aucune” rather than unavailable.
- System RAID role is inferred from filesystem/mount information where available.
- RAID device naming/translations improved for system arrays.

### Fixed
- SMART health can be reported for the TerraMaster USB system disk without exposing bogus 0 °C temperature or unsupported ATA counters.
- TerraMaster system RAID metadata with 24 logical slots no longer implies 24 expected physical disks/degraded hardware in the primary UI.

## [1.0.0] - 2026-08-01

First stable release.

### Added
- Local SSH monitoring with host-key verification.
- System, CPU, memory and temperature sensors.
- Dynamic physical disk and SMART monitoring.
- RAID and volume monitoring.
- Network interface counters and throughput.
- SSH, Telnet and SNMP service detection.
- Shared-folder discovery.
- SMB, NFS and AFP protocol detection.
- Secure general and per-share HTML pages.
- English and French translations.

### Changed
- Shared-folders summary displays the number of shares.
- Individual share capacities are displayed in GB rather than raw bytes.
- Share links include the configured username where appropriate.
- Improved Home Assistant device hierarchy and diagnostics.

[1.1.2]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.1...v1.1.2
[1.1.0]: https://github.com/minimicro34/ha-terramaster/compare/v1.0.0...v1.1.0
[1.1.0-beta2]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.0-beta1...v1.1.0-beta2
[1.1.0-beta1]: https://github.com/minimicro34/ha-terramaster/compare/v1.0.0...v1.1.0-beta1
[1.0.0]: https://github.com/minimicro34/ha-terramaster/releases/tag/v1.0.0
