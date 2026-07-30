"""TerraMaster TOS 4 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import TerraMasterApiClient
from .const import CONF_HOST_KEY, PLATFORMS
from .coordinator import TerraMasterDataUpdateCoordinator

type TerraMasterConfigEntry = ConfigEntry[TerraMasterDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TerraMasterConfigEntry) -> bool:
    """Set up TerraMaster from a config entry."""
    client = TerraMasterApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        host_key=entry.data.get(CONF_HOST_KEY),
    )
    coordinator = TerraMasterDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TerraMasterConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
