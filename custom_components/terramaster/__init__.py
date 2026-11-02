"""TerraMaster TOS 4 integration."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import TerraMasterApiClient
from .const import CONF_HOST_KEY, CONF_SHARE_TOKEN, DOMAIN, PLATFORMS
from .coordinator import TerraMasterDataUpdateCoordinator
from .share import TerraMasterShareView, share_page_url

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
LINK_EXPIRATION = timedelta(minutes=5)
GET_SHARE_LINK = "get_share_link"
GET_SHARE_LINK_SCHEMA = vol.Schema(
    {vol.Optional("entry_id"): cv.string, vol.Optional("share"): cv.string}
)

type TerraMasterConfigEntry = ConfigEntry[TerraMasterDataUpdateCoordinator]


async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    """Set up the TerraMaster integration."""
    hass.http.register_view(TerraMasterShareView(hass))

    async def async_get_share_link(call: ServiceCall) -> ServiceResponse:
        """Return a short-lived authenticated link, never stored in entity state."""
        entries = hass.config_entries.async_entries(DOMAIN)
        entry_id = call.data.get("entry_id")
        if entry_id is not None:
            entries = [entry for entry in entries if entry.entry_id == entry_id]
        if len(entries) != 1:
            raise vol.Invalid("Specify a valid entry_id when multiple NAS exist")
        entry = entries[0]
        if not hasattr(entry, "runtime_data"):
            raise vol.Invalid("TerraMaster entry is not loaded")
        share = call.data.get("share")
        if share is not None and not any(
            item.name == share for item in entry.runtime_data.data.shares
        ):
            raise vol.Invalid("Unknown shared folder")
        path = share_page_url("", entry.entry_id, share)
        return {
            "url": async_sign_path(hass, path, LINK_EXPIRATION),
            "expires_in": int(LINK_EXPIRATION.total_seconds()),
        }

    hass.services.async_register(
        DOMAIN,
        GET_SHARE_LINK,
        async_get_share_link,
        schema=GET_SHARE_LINK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerraMasterConfigEntry,
) -> bool:
    """Set up TerraMaster from a config entry."""
    if CONF_SHARE_TOKEN in entry.data:
        updated_data = dict(entry.data)
        updated_data.pop(CONF_SHARE_TOKEN)
        hass.config_entries.async_update_entry(entry, data=updated_data)

    client = TerraMasterApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        host_key=entry.data.get(CONF_HOST_KEY),
    )

    coordinator = TerraMasterDataUpdateCoordinator(
        hass,
        client,
    )

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
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
