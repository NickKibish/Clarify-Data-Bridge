"""The Clarify Data Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from datetime import timedelta

from .clarify_client import (
    ClarifyClient,
    ClarifyAuthenticationError,
    ClarifyConnectionError,
)
from .coordinator import ClarifyDataCoordinator
from .data_update_coordinator import ClarifyDataUpdateCoordinator
from .entity_listener import ClarifyEntityListener
from .signal_manager import ClarifySignalManager
from .item_manager import ClarifyItemManager
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
    DEFAULT_DATA_UPDATE_INTERVAL,
    DEFAULT_LOOKBACK_HOURS,
    SUPPORTED_DOMAINS,
    ENTRY_DATA_CLIENT,
    ENTRY_DATA_COORDINATOR,
    ENTRY_DATA_LISTENER,
    ENTRY_DATA_SIGNAL_MANAGER,
    ENTRY_DATA_ITEM_MANAGER,
    ENTRY_DATA_DATA_UPDATE_COORDINATOR,
    SERVICE_PUBLISH_ENTITY,
    SERVICE_PUBLISH_ENTITIES,
    SERVICE_PUBLISH_ALL_TRACKED,
    SERVICE_UPDATE_ITEM_VISIBILITY,
    SERVICE_PUBLISH_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_IDS,
    ATTR_VISIBLE,
    ATTR_LABELS,
    ATTR_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


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

    # Initialize item manager
    item_manager = ClarifyItemManager(
        hass=hass,
        client=client,
        signal_manager=signal_manager,
        auto_publish=False,  # Manual publishing by default
        default_visible=True,
    )

    # Initialize data update coordinator (for reading data from Clarify)
    data_update_coordinator = ClarifyDataUpdateCoordinator(
        hass=hass,
        client=client,
        integration_id=integration_id,
        update_interval=timedelta(seconds=DEFAULT_DATA_UPDATE_INTERVAL),
        lookback_hours=DEFAULT_LOOKBACK_HOURS,
    )

    # Store components
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_DATA_CLIENT: client,
        ENTRY_DATA_COORDINATOR: coordinator,
        ENTRY_DATA_SIGNAL_MANAGER: signal_manager,
        ENTRY_DATA_LISTENER: listener,
        ENTRY_DATA_ITEM_MANAGER: item_manager,
        ENTRY_DATA_DATA_UPDATE_COORDINATOR: data_update_coordinator,
    }

    # Register services (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_PUBLISH_ENTITY):
        await _async_register_services(hass)

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


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    import voluptuous as vol
    from homeassistant import config_validation as cv

    async def handle_publish_entity(call):
        """Handle publish_entity service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        visible = call.data.get(ATTR_VISIBLE, True)
        labels = call.data.get(ATTR_LABELS)

        # Find the item manager from any active integration instance
        item_manager = _get_item_manager(hass)
        if not item_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            item_id = await item_manager.async_publish_entity(
                entity_id=entity_id,
                visible=visible,
                labels=labels,
            )
            _LOGGER.info("Published entity %s as item %s", entity_id, item_id)
        except Exception as err:
            _LOGGER.error("Failed to publish entity %s: %s", entity_id, err)

    async def handle_publish_entities(call):
        """Handle publish_entities service call."""
        entity_ids = call.data[ATTR_ENTITY_IDS]
        visible = call.data.get(ATTR_VISIBLE, True)
        labels = call.data.get(ATTR_LABELS)

        item_manager = _get_item_manager(hass)
        if not item_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            result = await item_manager.async_publish_multiple_entities(
                entity_ids=entity_ids,
                visible=visible,
                labels=labels,
            )
            _LOGGER.info("Published %d entities as items", len(result))
        except Exception as err:
            _LOGGER.error("Failed to publish entities: %s", err)

    async def handle_publish_all_tracked(call):
        """Handle publish_all_tracked service call."""
        visible = call.data.get(ATTR_VISIBLE, True)
        labels = call.data.get(ATTR_LABELS)

        item_manager = _get_item_manager(hass)
        if not item_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            result = await item_manager.async_publish_all_tracked(
                visible=visible,
                labels=labels,
            )
            _LOGGER.info("Published %d tracked entities as items", len(result))
        except Exception as err:
            _LOGGER.error("Failed to publish tracked entities: %s", err)

    async def handle_update_item_visibility(call):
        """Handle update_item_visibility service call."""
        entity_id = call.data[ATTR_ENTITY_ID]
        visible = call.data[ATTR_VISIBLE]

        item_manager = _get_item_manager(hass)
        if not item_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            await item_manager.async_update_item_visibility(
                entity_id=entity_id,
                visible=visible,
            )
            _LOGGER.info("Updated visibility for %s to %s", entity_id, visible)
        except Exception as err:
            _LOGGER.error("Failed to update visibility for %s: %s", entity_id, err)

    async def handle_publish_domain(call):
        """Handle publish_domain service call."""
        domain = call.data[ATTR_DOMAIN]
        visible = call.data.get(ATTR_VISIBLE, True)
        labels = call.data.get(ATTR_LABELS)

        item_manager = _get_item_manager(hass)
        if not item_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        # Get all entities in the domain
        entity_ids = [
            state.entity_id
            for state in hass.states.async_all()
            if state.entity_id.startswith(f"{domain}.")
        ]

        try:
            result = await item_manager.async_publish_multiple_entities(
                entity_ids=entity_ids,
                visible=visible,
                labels=labels,
            )
            _LOGGER.info("Published %d entities from domain %s", len(result), domain)
        except Exception as err:
            _LOGGER.error("Failed to publish domain %s: %s", domain, err)

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH_ENTITY,
        handle_publish_entity,
        schema=vol.Schema({
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Optional(ATTR_VISIBLE, default=True): cv.boolean,
            vol.Optional(ATTR_LABELS): dict,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH_ENTITIES,
        handle_publish_entities,
        schema=vol.Schema({
            vol.Required(ATTR_ENTITY_IDS): cv.entity_ids,
            vol.Optional(ATTR_VISIBLE, default=True): cv.boolean,
            vol.Optional(ATTR_LABELS): dict,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH_ALL_TRACKED,
        handle_publish_all_tracked,
        schema=vol.Schema({
            vol.Optional(ATTR_VISIBLE, default=True): cv.boolean,
            vol.Optional(ATTR_LABELS): dict,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_ITEM_VISIBILITY,
        handle_update_item_visibility,
        schema=vol.Schema({
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_VISIBLE): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH_DOMAIN,
        handle_publish_domain,
        schema=vol.Schema({
            vol.Required(ATTR_DOMAIN): cv.string,
            vol.Optional(ATTR_VISIBLE, default=True): cv.boolean,
            vol.Optional(ATTR_LABELS): dict,
        }),
    )

    _LOGGER.info("Registered Clarify Data Bridge services")


def _get_item_manager(hass: HomeAssistant) -> ClarifyItemManager | None:
    """Get the item manager from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_ITEM_MANAGER in entry_data:
            return entry_data[ENTRY_DATA_ITEM_MANAGER]

    return None
