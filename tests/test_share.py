"""Tests for TerraMaster shared-folder connection links."""

from types import SimpleNamespace
from unittest.mock import Mock

from aiohttp.test_utils import make_mocked_request
from homeassistant.const import CONF_HOST

from custom_components.terramaster.const import DOMAIN
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


async def test_share_view() -> None:
    """The authenticated landing page presents actions and storage details."""
    hass = Mock()
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(
        domain=DOMAIN,
        data={CONF_HOST: "nas.local"},
        runtime_data=SimpleNamespace(data=_storage_data()),
    )
    request = make_mocked_request(
        "GET",
        "/api/terramaster/share?entry_id=entry-1",
        headers={"Accept-Language": "fr-FR,fr;q=0.9"},
    )

    response = await TerraMasterShareView(hass).get(request)

    assert response.status == 200
    assert 'href="smb://nas.local/My%20share"' in response.text
    assert 'href="nfs://nas.local/mnt/md0/My%20share"' in response.text
    assert "afp://" not in response.text
    assert "My share" in response.text
    assert "/mnt/md0/My share" in response.text
    assert "Ouvrir en SMB / CIFS" in response.text
    assert "vg0-lv0" in response.text
    assert "md0 · RAID1" in response.text
    assert "820.00 GB" in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
