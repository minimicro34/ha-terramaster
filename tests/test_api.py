"""Tests for the TerraMaster API parser."""

from custom_components.terramaster.api import TerraMasterApiClient

SAMPLE = """\
hostname=tnas
model=F4-220
tos_version=4.2.41
uptime=86400
mem_total=1000
mem_available=250
cpu=100 0 50 850 0 0 0 0
temperature=42500
disk=/dev/md0 1000 500 /Volume1
disk=/dev/md0 1000 500 /mnt/bind
disk=/dev/md1 2000 500 /Volume2
"""


def _client() -> TerraMasterApiClient:
    return TerraMasterApiClient("nas.local", 9222, "user", "password")


def test_parse_output() -> None:
    """A TOS snapshot is parsed and normalized."""
    client = _client()
    first = client._parse_output(SAMPLE)  # noqa: SLF001
    second = client._parse_output(  # noqa: SLF001
        SAMPLE.replace("cpu=100 0 50 850", "cpu=150 0 100 950")
    )

    assert first.hostname == "tnas"
    assert first.model == "F4-220"
    assert first.tos_version == "4.2.41"
    assert first.uptime == 86400
    assert first.memory_usage == 75.0
    assert first.temperature == 42.5
    assert first.disk_usage == 33.3
    assert first.cpu_usage is None
    assert second.cpu_usage == 50.0


def test_parse_missing_values() -> None:
    """Missing optional system files do not fail an update."""
    data = _client()._parse_output("hostname=tnas\n")  # noqa: SLF001

    assert data.hostname == "tnas"
    assert data.model is None
    assert data.cpu_usage is None
    assert data.disk_usage is None
