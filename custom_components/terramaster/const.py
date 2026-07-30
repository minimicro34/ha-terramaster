"""Constants for the TerraMaster TOS integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "terramaster"

DEFAULT_NAME: Final = "TerraMaster"
DEFAULT_PORT: Final = 9222
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)

CONF_HOST_KEY: Final = "host_key"

PLATFORMS: Final = ["sensor"]
