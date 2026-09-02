# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

---

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

[1.1.0-beta1]: https://github.com/minimicro34/ha-terramaster/compare/v1.0.0...v1.1.0-beta1
