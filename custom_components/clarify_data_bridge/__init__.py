"""The Clarify Data Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .clarify_client import (
    ClarifyClient,
    ClarifyAuthenticationError,
    ClarifyConnectionError,
)
from .coordinator import ClarifyDataCoordinator
from .entity_listener import ClarifyEntityListener
from .signal_manager import ClarifySignalManager
from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INTEGRATION_ID,
    CONF_BATCH_INTERVAL,
    CONF_MAX_BATCH_SIZE,
    CONF_INCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    DEFAULT_BATCH_INTERVAL,
    DEFAULT_MAX_BATCH_SIZE,
    SUPPORTED_DOMAINS,
    ENTRY_DATA_CLIENT,
    ENTRY_DATA_COORDINATOR,
    ENTRY_DATA_LISTENER,
    ENTRY_DATA_SIGNAL_MANAGER,
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

    client_id = entry.data[CONF_CLIENT_ID]
    client_secret = entry.data[CONF_CLIENT_SECRET]
    integration_id = entry.data[CONF_INTEGRATION_ID]

    # Get optional configuration
    batch_interval = entry.data.get(CONF_BATCH_INTERVAL, DEFAULT_BATCH_INTERVAL)
    max_batch_size = entry.data.get(CONF_MAX_BATCH_SIZE, DEFAULT_MAX_BATCH_SIZE)
    include_domains = entry.data.get(CONF_INCLUDE_DOMAINS, SUPPORTED_DOMAINS)
    exclude_entities = entry.data.get(CONF_EXCLUDE_ENTITIES, [])

    _LOGGER.debug("Setting up Clarify Data Bridge integration for: %s", integration_id)

    # Initialize Clarify API client with OAuth 2.0 credentials
    client = ClarifyClient(
        client_id=client_id,
        client_secret=client_secret,
        integration_id=integration_id,
    )

    try:
        # Establish connection and verify credentials
        await client.async_connect()
        await client.async_verify_connection()
        _LOGGER.info("Successfully connected to Clarify API for integration: %s", integration_id)
    except ClarifyAuthenticationError as err:
        _LOGGER.error("Authentication failed for integration %s: %s", integration_id, err)
        raise ConfigEntryNotReady(f"Authentication failed: {err}") from err
    except ClarifyConnectionError as err:
        _LOGGER.error("Connection failed for integration %s: %s", integration_id, err)
        raise ConfigEntryNotReady(f"Could not connect to Clarify: {err}") from err
    except Exception as err:
        _LOGGER.error("Unexpected error setting up integration %s: %s", integration_id, err)
        raise ConfigEntryNotReady(f"Setup failed: {err}") from err

    # Initialize data coordinator
    coordinator = ClarifyDataCoordinator(
        hass=hass,
        client=client,
        batch_interval=batch_interval,
        max_batch_size=max_batch_size,
    )

    # Initialize signal manager
    signal_manager = ClarifySignalManager(
        hass=hass,
        client=client,
        integration_id=integration_id,
    )

    # Initialize entity listener
    listener = ClarifyEntityListener(
        hass=hass,
        coordinator=coordinator,
        signal_manager=signal_manager,
        include_domains=include_domains,
        exclude_entities=exclude_entities,
    )

    # Store components
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_DATA_CLIENT: client,
        ENTRY_DATA_COORDINATOR: coordinator,
        ENTRY_DATA_SIGNAL_MANAGER: signal_manager,
        ENTRY_DATA_LISTENER: listener,
    }

    # Start coordinator and listener
    await coordinator.start()
    await listener.async_start()

    # Set up platforms
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "Clarify Data Bridge integration setup completed for: %s (tracking %d entities)",
        integration_id,
        listener.tracked_entity_count,
    )
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

    # Clean up resources
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)

        # Stop listener
        listener = entry_data.get(ENTRY_DATA_LISTENER)
        if listener:
            await listener.async_stop()
            _LOGGER.debug("Stopped entity listener")

        # Stop coordinator (sends remaining data)
        coordinator = entry_data.get(ENTRY_DATA_COORDINATOR)
        if coordinator:
            await coordinator.stop()
            _LOGGER.debug("Stopped data coordinator")

        # Close client
        client = entry_data.get(ENTRY_DATA_CLIENT)
        if client:
            client.close()
            _LOGGER.debug("Closed Clarify client connection")

        _LOGGER.info("Clarify Data Bridge integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
