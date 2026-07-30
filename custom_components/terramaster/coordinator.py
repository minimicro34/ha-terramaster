"""Data update coordinator for TerraMaster TOS."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TerraMasterApiClient,
    TerraMasterAuthenticationError,
    TerraMasterError,
    TerraMasterHostKeyError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import TerraMasterData

_LOGGER = logging.getLogger(__name__)


class TerraMasterDataUpdateCoordinator(DataUpdateCoordinator[TerraMasterData]):
    """Coordinate updates from a TerraMaster NAS."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: TerraMasterApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> TerraMasterData:
        try:
            return await self.client.async_get_data()
        except (TerraMasterAuthenticationError, TerraMasterHostKeyError) as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TerraMasterError as err:
            raise UpdateFailed(f"Error communicating with TerraMaster: {err}") from err
