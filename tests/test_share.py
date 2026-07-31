"""Tests for TerraMaster shared-folder connection links."""

from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp.test_utils import make_mocked_request
from homeassistant.const import CONF_HOST

from custom_components.terramaster.const import DOMAIN
from custom_components.terramaster.models import TerraMasterShare
from custom_components.terramaster.share import (
    TerraMasterShareView,
    share_connection_urls,
    share_page_url,
)


def _share() -> TerraMasterShare:
    return TerraMasterShare(
        name="My share",
        path="/mnt/md0/My share",
        device="/dev/mapper/vg0-lv0",
        share_type="public",
        hidden=False,
        recycle_bin=True,
        protocols=("smb", "nfs"),
    )


def test_share_urls() -> None:
    """Only available protocols produce correctly encoded URLs."""
    assert share_connection_urls("fe80::1", _share()) == {
        "smb": "smb://[fe80::1]/My%20share",
        "nfs": "nfs://[fe80::1]/mnt/md0/My%20share",
    }
    assert share_page_url("https://ha.example/", "entry 1", "My share") == (
        "https://ha.example/api/terramaster/share?entry_id=entry+1&share=My+share"
    )
    assert share_page_url("https://ha.example/", "entry 1") == (
        "https://ha.example/api/terramaster/share?entry_id=entry+1"
    )


async def test_share_view() -> None:
    """The authenticated landing page presents only active protocol links."""
    hass = Mock()
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(
        domain=DOMAIN,
        data={CONF_HOST: "nas.local"},
        runtime_data=SimpleNamespace(data=SimpleNamespace(shares=(_share(),))),
    )
    request = make_mocked_request(
        "GET",
        "/api/terramaster/share?entry_id=entry-1",
    )

    response = await TerraMasterShareView(hass).get(request)

    assert response.status == 200
    assert 'href="smb://nas.local/My%20share"' in response.text
    assert 'href="nfs://nas.local/mnt/md0/My%20share"' in response.text
    assert "afp://" not in response.text
    assert "My share" in response.text
    assert "/mnt/md0/My share" in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
