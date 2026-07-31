"""Shared parsing primitives for TOS command output."""

import re

MD_HEADER = re.compile(r"^(md\d+)\s*:\s*\w+\s+(\S+)\s+(.+)$")
MD_STATUS = re.compile(r"\[(\d+)/(\d+)]\s+\[([U_]+)]")
MD_MEMBER = re.compile(r"\b([a-z]+\d+)\[\d+]")
SMART_ATTRIBUTE = re.compile(r"^\s*(\d+)\s+\S+.*?\s+(\d+)\s*$")


def as_int(value: str | None, *, default: int | None = None) -> int | None:
    """Parse an integer, returning a default for missing or invalid input."""
    try:
        return int(value) if value else default
    except ValueError:
        return default


def as_float(value: str | None) -> float | None:
    """Parse a float from optional text."""
    try:
        return float(value) if value else None
    except ValueError:
        return None


def percentage(used: int, total: int) -> float | None:
    """Return a bounded percentage."""
    if total <= 0:
        return None
    return round(max(0.0, min(100.0, used * 100 / total)), 1)


def sync_progress(value: str | None) -> float | None:
    """Parse the Linux MD completed/total sync representation."""
    if not value or value == "none":
        return None
    completed, separator, total = value.partition("/")
    if not separator:
        return None
    completed_value = as_int(completed)
    total_value = as_int(total)
    if completed_value is None or total_value is None:
        return None
    return percentage(completed_value, total_value)
