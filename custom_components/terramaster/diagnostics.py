"""Diagnostics support for TerraMaster TOS."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.core import HomeAssistant

from . import TerraMasterConfigEntry
from .const import CONF_HOST_KEY

TO_REDACT = {"host", "password", "username", CONF_HOST_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TerraMasterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator_data = asdict(entry.runtime_data.data)
    for share in coordinator_data["shares"]:
        share["name"] = REDACTED
        share["path"] = REDACTED
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "data": coordinator_data,
        "last_update_success": entry.runtime_data.last_update_success,
    }
