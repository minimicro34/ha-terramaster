"""Register the bundled TerraMaster Lovelace card."""

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_CARD_PATH = "/terramaster/terramaster-card.js"
_VERSION = json.loads(
    (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
)["version"]
_CARD_URL = f"{_CARD_PATH}?v={_VERSION}"
_LOCK_KEY = "terramaster_frontend_lock"
_PATH_KEY = "terramaster_frontend_path_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Expose the card and register it once in storage-mode Lovelace."""
    from homeassistant.components.http import StaticPathConfig

    async with hass.data.setdefault(_LOCK_KEY, asyncio.Lock()):
        if not hass.data.get(_PATH_KEY):
            await hass.http.async_register_static_paths(
                [StaticPathConfig(_CARD_PATH, str(Path(__file__).parent / "www" / "terramaster-card.js"),
                    False,)]
            )
            hass.data[_PATH_KEY] = True

        lovelace = hass.data.get("lovelace")
        if lovelace is None or lovelace.resource_mode != "storage":
            _LOGGER.info(
                "Register %s manually when using Lovelace YAML mode", _CARD_URL
            )
            return

        resources = lovelace.resources
        if not resources.loaded:
            await resources.async_load()
        matching = [
            item
            for item in resources.async_items()
            if urlsplit(item["url"]).path == _CARD_PATH
        ]
        if matching:
            for item in matching:
                if item["url"] != _CARD_URL or item.get("res_type") != "module":
                    await resources.async_update_item(
                        item["id"], {"url": _CARD_URL, "res_type": "module"}
                    )
            if len(matching) > 1:
                _LOGGER.warning("Duplicate TerraMaster card resources detected")
            return
        await resources.async_create_item({"url": _CARD_URL, "res_type": "module"})
