"""Config flow for TerraMaster TOS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import (
    TerraMasterApiClient,
    TerraMasterAuthenticationError,
    TerraMasterConnectionError,
    TerraMasterError,
)
from .const import CONF_HOST_KEY, DEFAULT_PORT, DOMAIN


class TerraMasterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TerraMaster."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(f"{host.lower()}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                host_key = await _async_validate_input(user_input | {CONF_HOST: host})
            except TerraMasterAuthenticationError:
                errors["base"] = "invalid_auth"
            except TerraMasterConnectionError:
                errors["base"] = "cannot_connect"
            except TerraMasterError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=host,
                    data=user_input | {CONF_HOST: host, CONF_HOST_KEY: host_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Start reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm new credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            updated = dict(self._reauth_entry.data) | user_input
            # Reauth is also explicit approval to trust the current key.
            updated.pop(CONF_HOST_KEY, None)
            try:
                updated[CONF_HOST_KEY] = await _async_validate_input(updated)
            except TerraMasterAuthenticationError:
                errors["base"] = "invalid_auth"
            except TerraMasterConnectionError:
                errors["base"] = "cannot_connect"
            except TerraMasterError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=updated,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )


def _schema(defaults: dict[str, Any] | None) -> vol.Schema:
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_PORT, default=values.get(CONF_PORT, DEFAULT_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


async def _async_validate_input(data: dict[str, Any]) -> str:
    client = TerraMasterApiClient(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )
    return await client.async_test_connection()
