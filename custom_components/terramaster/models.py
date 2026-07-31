"""Data models for the TerraMaster TOS integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TerraMasterDisk:
    """A physical disk installed in the NAS."""

    name: str
    model: str | None
    serial: str | None
    size: int | None
    state: str | None
    is_system: bool = False
    smart_status: str | None = None
    temperature: float | None = None
    power_on_hours: int | None = None
    power_cycle_count: int | None = None
    start_stop_count: int | None = None
    load_cycle_count: int | None = None
    spin_retry_count: int | None = None
    reallocated_sectors: int | None = None
    reallocated_events: int | None = None
    pending_sectors: int | None = None
    offline_uncorrectable: int | None = None
    udma_crc_errors: int | None = None


@dataclass(frozen=True, slots=True)
class TerraMasterRaid:
    """A Linux MD RAID array."""

    name: str
    level: str
    state: str | None
    size: int | None
    members: tuple[str, ...]
    expected_devices: int | None
    active_devices: int | None
    degraded_devices: int | None
    sync_action: str | None = None
    sync_progress: float | None = None
    is_system: bool = False


@dataclass(frozen=True, slots=True)
class TerraMasterVolume:
    """A mounted user volume."""

    name: str
    device: str
    filesystem: str
    mountpoint: str
    size: int
    used: int
    available: int
    usage: float


@dataclass(frozen=True, slots=True)
class TerraMasterData:
    """A snapshot of TerraMaster system data."""

    hostname: str
    model: str | None
    tos_version: str | None
    uptime: int | None
    boot_time: int | None
    cpu_usage: float | None
    memory_usage: float | None
    temperature: float | None
    disk_usage: float | None
    disks: tuple[TerraMasterDisk, ...] = ()
    raids: tuple[TerraMasterRaid, ...] = ()
    volumes: tuple[TerraMasterVolume, ...] = ()
