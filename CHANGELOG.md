# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

---

## [1.2.0-beta2] - 2026-11-27

### Fixed
- Preserve SMART permission errors as a sudo fallback signal even when a permissive SCSI query returns a health status.
- Track missing NAS model collection independently of SMART and shared folders.
- Preserve direct-first collection for newer TOS versions and direct-only collection for root.

### Validation
- Add regression tests for the partial SCSI response and missing model observed on the F2-210 running TOS 4.2.41.
- Ruff and Mypy passed.
- All 21 Python tests passed locally; Python test coverage: 82.42%.
- PR #9 CI passed.
- TOS 4 and TOS 7 hardware retesting pending.

## [1.2.0-beta1] - 2026-11-27

This pre-release introduces TOS 7 support and NVMe disk monitoring, contributed by [@dkrichun](https://github.com/dkrichun) in [PR #8](https://github.com/minimicro34/ha-terramaster/pull/8).

### Changed
- Privileged collection (SMART, shared folders, TOS version) now tries a direct run first and falls back to `sudo`. On TOS 7 the shell user can access SMART data directly, while `sudo` restricts device access; older TOS versions continue to use `sudo`. SMART and shared-folder collection are tracked independently (a mode providing only one of them no longer suppresses the fallback for the other), partial outputs are merged, version-only output is preserved, and transient SSH failures are retried on the next poll instead of disabling collection.

### Added
- NVMe disk discovery and monitoring: SMART health, temperature, power-on hours and power cycles via the controller's first namespace.
- Per-disk total data read/written sensors computed from SMART: SATA attributes 241/242 only when named "Total_LBAs_Written/Read" (512-byte LBA semantics are vendor-specific) and NVMe "Data Units Read/Written", exposed in gigabytes. Power-on time is shown in days.
- Additional TOS version file locations for newer TOS releases, including `/etc/tos/config/login_title.conf` and `/etc/issue` on TOS 7; the parser prefers a line mentioning "TOS" so the Ubuntu version in `/etc/issue` is not picked instead (verified on TOS 7.0.1536).

### Validation
- Direct-first privileged collection, sudo fallback, unavailable mode and NVMe SMART parsing.
- Partial privileged collection (SMART direct + shares via sudo), version-only output, root direct-only mode and retry after transient SSH failures.
- SATA LBA totals accepted only for known counter names, and NVMe data units parsing.
- Ruff and Mypy passed.
- JavaScript syntax and card smoke tests passed.
- HACS and Hassfest validation passed.
- All 19 Python tests passed; Python test coverage: 82.32%.
- TOS 7.0.1536 hardware testing reported by the contributor; TOS 4 regression testing pending.

## [1.1.6] - 2026-11-04

### Fixed
- Replace the remaining deprecated `async_get_device()` call in the shared-folder view with the config-entry-scoped `async_get_device_by_identifier()` API.
- Ensure compatibility with Home Assistant 2027.8.0 and later.

### Changed
- Update the README to prioritize installation through the default HACS catalog.
- Retain custom repository installation as an alternative.

### Validation
- Add regression tests for the config-entry-scoped device registry lookup.
- Ruff and Mypy passed.
- All 11 Python tests passed.
- Python test coverage: **80.43%** (minimum required: 80%).
- JavaScript syntax and card smoke tests passed.
- HACS and Hassfest validation passed.

## [1.1.5] - 2026-11-03

This release marks the official inclusion of TerraMaster TOS in the HACS default catalog, following the successful review and approval of [HACS PR #10598](https://github.com/hacs/default/pull/10598).

### Fixed
- Replace deprecated device registry lookup with the config-entry-scoped API for compatibility with future Home Assistant versions (introduced in v1.1.4).
- Discover TerraMaster entities through the Home Assistant entity registry, regardless of translated entity IDs.
- Resolve monitoring data using stable entity unique IDs and isolate entities belonging to individual NAS configurations.
- Improve dashboard compatibility with Home Assistant Sections views using native full-width grid options.
- Display NAS uptime and disk operating durations in human-readable days, hours and minutes.
- Limit numeric readings to two decimal places and automatically convert large storage capacities from GB to TB.

### Changed
- Improve dashboard responsiveness and readability in Sections and Panel views.
- Add the official NAS and servers integration category to the manifest.
- Update dashboard configuration and usage documentation.
- Consolidate frontend JavaScript checks into the main quality CI job.

### Validation
- Extend JavaScript regression tests for localized entity discovery, multiple NAS configurations, numeric formatting, uptime and dashboard sizing.
- Validate collapsible sections and secure signed shared-folder links.
- Quality CI checks passed.
- Python test coverage: **80.43%** (minimum required: 80%).
- HACS and Hassfest validation passed.
- Dashboard tested on TerraMaster F2-210 running TOS 4.2.41.
- Sections and Panel layouts validated in Home Assistant.
- Secure shared-folder navigation verified.

## [1.1.5-beta2] - 2026-11-03

### Fixed
- Request full section width using Home Assistant's native `columns: full` grid option instead of a fixed 12-column allocation.
- Improve compatibility with Sections dashboards while preserving Panel view support.
- Limit numeric sensor readings to two decimal places.
- Automatically convert large storage capacities from GB to TB.
- Prevent unwanted line wrapping in disk, RAID, volume and network details.

### Changed
- Improve dashboard readability without modifying underlying Home Assistant sensor values.
- Update README configuration examples for Sections and Panel views.
- Clarify automatic entity discovery and optional configuration settings.
- Update release history and development documentation.

### Validation
- Update JavaScript regression tests for native full-width grid options.
- Add tests for numeric formatting and automatic storage unit conversion.
- Preserve regression tests for localized entity discovery, NAS isolation, collapsible sections and signed shared-folder links.
- Automated Python and JavaScript checks passed.
- GitHub Actions CI passed.
- Entity discovery and secure shared-folder navigation validated on TerraMaster F2-210 running TOS 4.2.41.
- Full-width rendering in Sections dashboards pending at the time of this pre-release.

## [1.1.5-beta1] - 2026-11-03

### Fixed
- Replace entity name and prefix-based discovery with Home Assistant entity and device registry lookups.
- Support localized and automatically generated entity IDs.
- Identify monitoring metrics using stable entity unique IDs instead of language-dependent entity names.
- Discover disk, RAID, volume, network and service sensors without requiring a common NAS prefix.
- Scope automatic entity discovery to a single TerraMaster configuration entry to prevent mixing sensors from multiple NAS devices.
- Improve Home Assistant Sections dashboard compatibility by declaring a 12-column grid layout.

### Changed
- Reduce reliance on manually configured entity prefixes.
- Preserve collapsible monitoring sections and secure shared-folder access.
- Build on the device registry compatibility improvements introduced in v1.1.4.

### Validation
- Add regression tests for localized entity IDs and registry-based discovery.
- Verify isolation between multiple TerraMaster configuration entries.
- Validate grid options for Home Assistant Sections dashboards.
- Existing Python and JavaScript tests passed.
- GitHub Actions CI passed.
- Real-world dashboard validation pending at the time of this pre-release.

## [1.1.4] - 2026-11-03

### Fixed
- Replace the deprecated `async_get_device()` lookup with `async_get_device_by_identifier()`.
- Scope device registry lookups to the corresponding TerraMaster configuration entry.
- Address the device registry API deprecation scheduled for removal in Home Assistant 2027.8.0.

### Changed
- Preserve existing device registration and entity associations.
- No configuration changes or entity renaming required.
- Preserve existing dashboard functionality and secure shared-folder access.

### Validation
- Existing automated tests passed.
- Quality CI checks passed.
- HACS and Hassfest validation passed.

## [1.1.3] - 2026-11-03

This release introduces the bundled TerraMaster Lovelace dashboard, providing a unified monitoring interface with secure shared-folder navigation.

### Added
- Introduce the bundled `custom:terramaster-card` Lovelace dashboard.
- Display CPU, memory, temperature, storage and system information.
- Add collapsible sections for disks, SMART attributes, RAID arrays, volumes, network interfaces and services.
- Add secure shared-folder navigation using short-lived signed URLs without persistent access tokens.

### Changed
- Display the NAS model in the dashboard header.
- Preserve expanded sections during dashboard updates.
- Update README with dashboard installation, configuration and usage instructions.

### Fixed
- Replace legacy persistent shared-folder access URLs with secure signed links.

### Validation
- Add JavaScript regression tests for card rendering, HTML escaping, collapsible sections and signed shared-folder navigation.
- Introduce a minimum Python test coverage threshold of 80% in CI and generate a coverage XML report.
- Ruff and Mypy passed.
- All 11 Python tests passed.
- All 4 JavaScript tests passed.
- Python test coverage: **80.43%** (minimum required: 80%).
- HACS and Hassfest validation passed.
- All GitHub Actions CI checks passed.

## [1.1.2] - 2026-11-02

This release addresses the security and privacy requirements identified during the [HACS inclusion review](https://github.com/hacs/default/pull/10598), introducing authenticated shared-folder access, short-lived signed URLs and improved diagnostics protection.

### Added
- Introduce the `terramaster.get_share_link` action to generate secure signed shared-folder URLs.
- Support signed URLs for both the shared-folder index and individual shared folders.
- Add secure navigation back to the shared-folder index.

### Changed
- Remove the persistent Visit link from the Home Assistant device page.
- Preserve existing SMB, NFS and AFP connection URLs.
- Update README with secure shared-folder access instructions.

### Security
- Require Home Assistant authentication for shared-folder pages.
- Replace persistent access tokens with short-lived signed URLs valid for five minutes.
- Remove legacy access tokens from existing configuration entries automatically.
- Redact sensitive information from integration diagnostics.
- Prevent generated URLs from exposing authentication credentials.

### Validation
- Ruff and Mypy passed.
- Python automated tests passed.
- HACS and Hassfest validation passed.
- All GitHub Actions CI checks passed.

## [1.1.1] - 2026-10-25

### Changed
- Update the AsyncSSH dependency requirement from `==2.24.0` to `>=2.24.0`.

### Fixed
- Resolve Hassfest validation issues related to a dependency already managed by Home Assistant.
- Resolve Mypy type-checking issues in the initial configuration and reauthentication flows without changing runtime behavior.

### Validation
- Quality CI checks passed.
- HACS and Hassfest validation passed.
- All GitHub Actions CI checks passed.

## [1.1.0] - 2026-09-02

This release significantly expands TerraMaster NAS monitoring with improved SMART data collection, RAID monitoring and shared-folder navigation.

### Added
- Add permissive SCSI SMART fallback for system disks.
- Expose RAID member disk information.
- Detect and monitor TOS system and swap RAID arrays.
- Add direct access to shared-folder pages through the Home Assistant device Visit link.
- Add navigation between shared-folder pages and the NAS device.

### Changed
- Prioritize SAT SMART commands before attempting fallback methods.
- Expose essential monitoring information for system disks.
- Separate RAID synchronization actions from synchronization progress.
- Display idle RAID synchronization states as `None` or `Aucune`, depending on the selected language.
- Improve automatic identification of system RAID array purposes.
- Improve entity naming and English and French translations.
- Improve shared-folder navigation with a Back to NAS link.

### Fixed
- Handle USB system disk SMART data without exposing invalid temperature readings or unsupported ATA counters.
- Prevent misleading degraded RAID states caused by unused logical disk slots.

### Validation
- Add automated regression tests for SMART parsing, system disks, RAID arrays, synchronization and shared-folder handling.
- Tested on TerraMaster F2-210 running TOS 4.2.41 with Home Assistant.
- Other TerraMaster models and TOS versions were not validated at the time of this release.

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

### Validation
- Automated tests covering SMART fallback, system disks, RAID details, synchronization display and share navigation added.

## [1.0.0] - 2026-08-01

First stable release of TerraMaster TOS for Home Assistant, providing comprehensive local NAS monitoring through a secure SSH connection.

### Added
- Local SSH communication with host key verification.
- NAS system information and uptime monitoring.
- CPU, memory and temperature monitoring.
- Dynamic disk discovery and SMART monitoring.
- RAID array and storage volume monitoring.
- Network interface statistics and throughput monitoring.
- SSH, Telnet and SNMP service detection.
- Shared-folder discovery and monitoring.
- SMB, NFS and AFP connection URLs.
- HTML pages for shared-folder information and navigation.
- English and French translations.

### Changed
- Include the number of shared folders in the monitoring summary.
- Standardize storage capacity readings in GB.
- Include the NAS username in supported connection URLs.
- Improve entity organization and diagnostic information.

[1.2.0-beta2]: https://github.com/minimicro34/ha-terramaster/compare/v1.2.0-beta1...v1.2.0-beta2
[1.2.0-beta1]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.6...v1.2.0-beta1
[1.1.6]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.5...v1.1.6
[1.1.5]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.4...v1.1.5
[1.1.5-beta2]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.5-beta1...v1.1.5-beta2
[1.1.5-beta1]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.4...v1.1.5-beta1
[1.1.4]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/minimicro34/ha-terramaster/compare/v1.0.0...v1.1.0
[1.1.0-beta2]: https://github.com/minimicro34/ha-terramaster/compare/v1.1.0-beta1...v1.1.0-beta2
[1.1.0-beta1]: https://github.com/minimicro34/ha-terramaster/compare/v1.0.0...v1.1.0-beta1
[1.0.0]: https://github.com/minimicro34/ha-terramaster/releases/tag/v1.0.0
