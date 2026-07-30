"""Data models for the TerraMaster TOS integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TerraMasterData:
    """A snapshot of TerraMaster system data."""

    hostname: str
    model: str | None
    tos_version: str | None
    uptime: int | None
    cpu_usage: float | None
    memory_usage: float | None
    temperature: float | None
    disk_usage: float | None
