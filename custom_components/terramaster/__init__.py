"""TerraMaster TOS 4 integration."""

from __future__ import annotations

import secrets

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .api import TerraMasterApiClient
from .const import CONF_HOST_KEY, CONF_SHARE_TOKEN, PLATFORMS
from .coordinator import TerraMasterDataUpdateCoordinator
from .share import (
    TerraMasterShareView,
    register_share_access,
    unregister_share_access,
)

type TerraMasterConfigEntry = ConfigEntry[TerraMasterDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TerraMaster integration."""
    hass.http.register_view(TerraMasterShareView(hass))
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
) -> bool:
    """Set up TerraMaster from a config entry."""
    share_token = entry.data.get(CONF_SHARE_TOKEN)

    if not isinstance(share_token, str) or not share_token:
        share_token = secrets.token_urlsafe(32)

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_SHARE_TOKEN: share_token,
            },
        )

    register_share_access(
        entry_id=entry.entry_id,
        host=str(entry.data[CONF_HOST]),
        username=str(entry.data[CONF_USERNAME]),
        token=share_token,
    )

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

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        unregister_share_access(entry.entry_id)

    return unload_ok
