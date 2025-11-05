"""Config flow for Clarify Data Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .clarify_client import (
    ClarifyClient,
    ClarifyAuthenticationError,
    ClarifyConnectionError,
)
from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INTEGRATION_ID,
    CONF_BATCH_INTERVAL,
    CONF_MAX_BATCH_SIZE,
    DEFAULT_NAME,
    DEFAULT_BATCH_INTERVAL,
    DEFAULT_MAX_BATCH_SIZE,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_INTEGRATION_ID): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect to Clarify.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client_id = data[CONF_CLIENT_ID]
    client_secret = data[CONF_CLIENT_SECRET]
    integration_id = data[CONF_INTEGRATION_ID]

    # Test Clarify API connection with OAuth 2.0 credentials
    try:
        client = ClarifyClient(
            client_id=client_id,
            client_secret=client_secret,
            integration_id=integration_id,
        )
        await client.async_connect()
        await client.async_verify_connection()
        _LOGGER.info("Successfully validated Clarify credentials for integration: %s", integration_id)
    except ClarifyAuthenticationError as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise InvalidAuth from err
    except ClarifyConnectionError as err:
        _LOGGER.error("Connection failed: %s", err)
        raise CannotConnect from err
    finally:
        # Clean up client resources
        if 'client' in locals():
            client.close()

    # Return info that you want to store in the config entry
    return {
        "title": f"{DEFAULT_NAME} ({integration_id})",
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Clarify Data Bridge."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = ERROR_CANNOT_CONNECT
            except InvalidAuth:
                errors["base"] = ERROR_INVALID_AUTH
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = ERROR_UNKNOWN
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_INTEGRATION_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Clarify Data Bridge."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_batch_interval = self.config_entry.data.get(
            CONF_BATCH_INTERVAL, DEFAULT_BATCH_INTERVAL
        )
        current_max_batch_size = self.config_entry.data.get(
            CONF_MAX_BATCH_SIZE, DEFAULT_MAX_BATCH_SIZE
        )

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BATCH_INTERVAL,
                    default=current_batch_interval,
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                vol.Optional(
                    CONF_MAX_BATCH_SIZE,
                    default=current_max_batch_size,
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=1000)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
