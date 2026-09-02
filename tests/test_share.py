"""Tests for TerraMaster shared-folder connection links."""

from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp.test_utils import make_mocked_request
from homeassistant.const import CONF_HOST, CONF_USERNAME

from custom_components.terramaster.const import CONF_SHARE_TOKEN, DOMAIN
from custom_components.terramaster.models import (
    TerraMasterRaid,
    TerraMasterShare,
    TerraMasterVolume,
)
from custom_components.terramaster.share import (
    TerraMasterShareView,
    resolve_share_storage,
    share_connection_urls,
    share_page_url,
)

SHARE_TOKEN = "test-share-token"


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
    assert share_connection_urls("nas.local", _share(), "admin") == {
        "smb": "smb://admin@nas.local/My%20share",
        "nfs": "nfs://nas.local/mnt/md0/My%20share",
    }
    assert share_page_url(
        "https://ha.example/",
        "entry 1",
        SHARE_TOKEN,
        "My share",
    ) == (
        "https://ha.example/api/terramaster/share?"
        "entry_id=entry+1&token=test-share-token&share=My+share"
    )
    assert share_page_url(
        "https://ha.example/",
        "entry 1",
        SHARE_TOKEN,
    ) == (
        "https://ha.example/api/terramaster/share?"
        "entry_id=entry+1&token=test-share-token"
    )


def _storage_data() -> SimpleNamespace:
    return SimpleNamespace(
        shares=(_share(),),
        volumes=(
            TerraMasterVolume(
                name="vg0-lv0",
                device="/dev/mapper/vg0-lv0",
                filesystem="btrfs",
                mountpoint="/mnt/md0",
                size=1_000_000_000_000,
                used=180_000_000_000,
                available=820_000_000_000,
                usage=18.0,
            ),
        ),
        raids=(
            TerraMasterRaid(
                name="md0",
                level="raid1",
                state="clean",
                size=1_000_000_000_000,
                members=("sdb4", "sdc4"),
                expected_devices=2,
                active_devices=2,
                degraded_devices=0,
            ),
        ),
    )


def test_resolve_share_storage() -> None:
    """A share is associated with its mounted volume and RAID array."""
    storage = resolve_share_storage(_storage_data(), _share())

    assert storage.volume is not None
    assert storage.volume.name == "vg0-lv0"
    assert storage.raid is not None
    assert storage.raid.name == "md0"


def _hass() -> Mock:
    hass = Mock()
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        data={
            CONF_HOST: "nas.local",
            CONF_USERNAME: "admin",
            CONF_SHARE_TOKEN: SHARE_TOKEN,
        },
        runtime_data=SimpleNamespace(data=_storage_data()),
    )
    return hass


async def test_share_view() -> None:
    """The landing page presents actions, storage details, and HA navigation."""
    request = make_mocked_request(
        "GET",
        "/api/terramaster/share?entry_id=entry-1&token=test-share-token",
        headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )

    response = await TerraMasterShareView(_hass()).get(request)

    assert response.status == 200
    assert 'href="smb://admin@nas.local/My%20share"' in response.text
    assert 'href="nfs://nas.local/mnt/md0/My%20share"' in response.text
    assert "afp://" not in response.text
    assert "My share" in response.text
    assert "/mnt/md0/My share" in response.text
    assert "Ouvrir avec SMB / CIFS" in response.text
    assert "vg0-lv0" in response.text
    assert "md0 · RAID1" in response.text
    assert "820.00 GB" in response.text
    assert "admin" in response.text
    assert '<a href="/">Retour à Home Assistant</a>' in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def test_share_detail_navigation() -> None:
    """A share detail page links back to the token-protected share index."""
    request = make_mocked_request(
        "GET",
        (
            "/api/terramaster/share?entry_id=entry-1&token=test-share-token"
            "&share=My+share"
        ),
        headers={"Accept-Language": "fr-FR"},
    )

    response = await TerraMasterShareView(_hass()).get(request)

    assert response.status == 200
    assert "← Partages TerraMaster" in response.text
    assert (
        'href="/api/terramaster/share?entry_id=entry-1&amp;token=test-share-token"'
        in response.text
    )
    assert "&amp;share=" not in response.text
    assert '<a href="/">Home Assistant ↗</a>' in response.text
