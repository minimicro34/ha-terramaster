"""Tests for the TerraMaster config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terramaster.const import CONF_HOST_KEY, DOMAIN


async def test_user_flow(hass: HomeAssistant) -> None:
    """A valid SSH configuration creates an entry with a pinned host key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    user_input = {
        CONF_HOST: "nas.local",
        CONF_PORT: 9222,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
    }
    with (
        patch(
            "custom_components.terramaster.config_flow._async_validate_input",
            return_value="ssh-ed25519 AAAA-test-key",
        ),
        patch("custom_components.terramaster.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "nas.local"
    assert result["data"][CONF_HOST_KEY] == "ssh-ed25519 AAAA-test-key"


async def test_duplicate_host_aborts(hass: HomeAssistant) -> None:
    """The same host and SSH port cannot be configured twice."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="nas.local",
        data={
            CONF_HOST: "nas.local",
            CONF_PORT: 9222,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
        unique_id="nas.local:9222",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "nas.local",
            CONF_PORT: 9222,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
