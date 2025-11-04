"""The Clarify Data Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_INTEGRATION_ID,
    ENTRY_DATA_CLIENT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Clarify Data Bridge integration from YAML configuration."""
    _LOGGER.info("Clarify Data Bridge integration loaded")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Clarify Data Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]
    integration_id = entry.data[CONF_INTEGRATION_ID]

    _LOGGER.debug("Setting up Clarify Data Bridge integration")

    # TODO: Initialize Clarify API client
    # client = ClarifyClient(api_key=api_key, integration_id=integration_id)

    try:
        # TODO: Verify API connection
        _LOGGER.info("Successfully connected to Clarify API")
    except Exception as err:
        _LOGGER.error("Failed to connect to Clarify API: %s", err)
        raise ConfigEntryNotReady(f"Could not connect to Clarify: {err}") from err

    # Store client
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_DATA_CLIENT: None,  # TODO: Store actual client
    }

    # Set up platforms
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Clarify Data Bridge integration setup completed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Clarify Data Bridge integration")

    # Check if integration data exists
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.debug("Integration data not found, nothing to unload")
        return True

    # Unload platforms
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Clarify Data Bridge integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
