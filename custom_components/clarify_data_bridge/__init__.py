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
from .entity_selector import EntitySelector, DataPriority
from .historical_sync import HistoricalDataSync
from .config_schema import ConfigurationManager
from .performance_tuning import PerformanceManager
from .health_monitor import IntegrationHealthMonitor
from .const import (
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_INTEGRATION_ID,
    CONF_BATCH_INTERVAL,
    CONF_MAX_BATCH_SIZE,
    CONF_INCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_INCLUDE_DEVICE_CLASSES,
    CONF_EXCLUDE_DEVICE_CLASSES,
    CONF_INCLUDE_PATTERNS,
    CONF_EXCLUDE_PATTERNS,
    CONF_MIN_PRIORITY,
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
    ENTRY_DATA_HISTORICAL_SYNC,
    ENTRY_DATA_CONFIG_MANAGER,
    ENTRY_DATA_PERFORMANCE_MANAGER,
    ENTRY_DATA_HEALTH_MONITOR,
    SERVICE_PUBLISH_ENTITY,
    SERVICE_PUBLISH_ENTITIES,
    SERVICE_PUBLISH_ALL_TRACKED,
    SERVICE_UPDATE_ITEM_VISIBILITY,
    SERVICE_PUBLISH_DOMAIN,
    SERVICE_SYNC_HISTORICAL,
    SERVICE_FLUSH_BUFFER,
    SERVICE_APPLY_TEMPLATE,
    SERVICE_SET_ENTITY_CONFIG,
    SERVICE_SET_PERFORMANCE_PROFILE,
    SERVICE_GET_HEALTH_REPORT,
    SERVICE_RESET_STATISTICS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_IDS,
    ATTR_VISIBLE,
    ATTR_LABELS,
    ATTR_DOMAIN,
    EVENT_BUFFER_FLUSHED,
    EVENT_TRANSMISSION_SUCCESS,
    EVENT_TRANSMISSION_FAILED,
    EVENT_HEALTH_STATUS_CHANGED,
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
    include_device_classes = entry.data.get(CONF_INCLUDE_DEVICE_CLASSES)
    exclude_device_classes = entry.data.get(CONF_EXCLUDE_DEVICE_CLASSES)
    include_patterns = entry.data.get(CONF_INCLUDE_PATTERNS)
    exclude_patterns = entry.data.get(CONF_EXCLUDE_PATTERNS)
    min_priority_str = entry.data.get(CONF_MIN_PRIORITY, "LOW")

    # Parse priority level
    try:
        min_priority = DataPriority[min_priority_str.upper()]
    except (KeyError, AttributeError):
        min_priority = DataPriority.LOW
        _LOGGER.warning("Invalid min_priority '%s', using LOW", min_priority_str)

    _LOGGER.debug("Setting up Clarify Data Bridge integration for: %s", integration_id)

    # Initialize Clarify API client with OAuth 2.0 credentials
    client = ClarifyClient(
        hass=hass,
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

    # Initialize entity selector for advanced entity discovery
    entity_selector = EntitySelector(hass=hass)
    await entity_selector.async_setup()
    _LOGGER.debug("Entity selector initialized")

    # Initialize data coordinator
    coordinator = ClarifyDataCoordinator(
        hass=hass,
        client=client,
        batch_interval=batch_interval,
        max_batch_size=max_batch_size,
    )

    # Initialize signal manager with entity selector for enhanced metadata
    signal_manager = ClarifySignalManager(
        hass=hass,
        client=client,
        integration_id=integration_id,
        entity_selector=entity_selector,
    )

    # Initialize entity listener with advanced discovery options
    listener = ClarifyEntityListener(
        hass=hass,
        coordinator=coordinator,
        signal_manager=signal_manager,
        entity_selector=entity_selector,
        include_domains=include_domains,
        exclude_entities=exclude_entities,
        include_device_classes=include_device_classes,
        exclude_device_classes=exclude_device_classes,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        min_priority=min_priority,
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

    # Initialize Phase 7: Advanced Features managers
    historical_sync = HistoricalDataSync(
        hass=hass,
        client=client,
        coordinator=coordinator,
    )

    config_manager = ConfigurationManager(hass=hass)

    performance_manager = PerformanceManager(hass=hass)

    health_monitor = IntegrationHealthMonitor(hass=hass)

    # Store components
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_DATA_CLIENT: client,
        ENTRY_DATA_COORDINATOR: coordinator,
        ENTRY_DATA_SIGNAL_MANAGER: signal_manager,
        ENTRY_DATA_LISTENER: listener,
        ENTRY_DATA_ITEM_MANAGER: item_manager,
        ENTRY_DATA_DATA_UPDATE_COORDINATOR: data_update_coordinator,
        ENTRY_DATA_HISTORICAL_SYNC: historical_sync,
        ENTRY_DATA_CONFIG_MANAGER: config_manager,
        ENTRY_DATA_PERFORMANCE_MANAGER: performance_manager,
        ENTRY_DATA_HEALTH_MONITOR: health_monitor,
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

    # Phase 7 Service Handlers

    async def handle_sync_historical(call):
        """Handle sync_historical service call."""
        from datetime import datetime
        from homeassistant.util import dt as dt_util

        entity_ids = call.data["entity_ids"]
        start_time_str = call.data["start_time"]
        end_time_str = call.data.get("end_time")
        batch_size = call.data.get("batch_size", 1000)
        batch_delay = call.data.get("batch_delay", 2.0)

        historical_sync = _get_historical_sync(hass)
        if not historical_sync:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            # Parse start_time
            if start_time_str.startswith("-"):
                # Relative time (e.g., "-7 days")
                parts = start_time_str.split()
                if len(parts) == 2:
                    amount = int(parts[0])
                    unit = parts[1]
                    if unit in ("day", "days"):
                        start_time = dt_util.utcnow() + timedelta(days=amount)
                    elif unit in ("hour", "hours"):
                        start_time = dt_util.utcnow() + timedelta(hours=amount)
                    else:
                        start_time = dt_util.parse_datetime(start_time_str)
                else:
                    start_time = dt_util.parse_datetime(start_time_str)
            else:
                start_time = dt_util.parse_datetime(start_time_str)

            # Parse end_time
            end_time = dt_util.parse_datetime(end_time_str) if end_time_str else None

            _LOGGER.info(
                "Starting historical sync for %d entities from %s to %s",
                len(entity_ids),
                start_time,
                end_time or "now",
            )

            await historical_sync.async_sync_historical_data(
                entity_ids=entity_ids,
                start_time=start_time,
                end_time=end_time,
                batch_size=batch_size,
                batch_delay=batch_delay,
            )

            _LOGGER.info("Historical sync completed successfully")

        except Exception as err:
            _LOGGER.error("Failed to sync historical data: %s", err)

    async def handle_flush_buffer(call):
        """Handle flush_buffer service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            await coordinator.manual_flush()
            hass.bus.async_fire(EVENT_BUFFER_FLUSHED)
            _LOGGER.info("Buffer flushed successfully")
        except Exception as err:
            _LOGGER.error("Failed to flush buffer: %s", err)

    async def handle_apply_template(call):
        """Handle apply_template service call."""
        template_name = call.data["template_name"]
        entity_ids = call.data["entity_ids"]

        config_manager = _get_config_manager(hass)
        if not config_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            config_manager.apply_template(template_name, entity_ids)
            _LOGGER.info(
                "Applied template '%s' to %d entities",
                template_name,
                len(entity_ids),
            )
        except Exception as err:
            _LOGGER.error("Failed to apply template: %s", err)

    async def handle_set_entity_config(call):
        """Handle set_entity_config service call."""
        from .config_schema import EntityConfig

        entity_id = call.data["entity_id"]
        transmission_interval = call.data.get("transmission_interval")
        aggregation_method = call.data.get("aggregation_method")
        aggregation_window = call.data.get("aggregation_window")
        priority = call.data.get("priority")
        buffer_strategy = call.data.get("buffer_strategy")

        config_manager = _get_config_manager(hass)
        if not config_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            # Build entity config
            config = EntityConfig(
                entity_id=entity_id,
                transmission_interval=transmission_interval,
                aggregation_method=aggregation_method,
                aggregation_window=aggregation_window,
                priority=priority,
                buffer_strategy=buffer_strategy,
            )

            config_manager.set_entity_config(entity_id, config)
            _LOGGER.info("Updated configuration for entity: %s", entity_id)

        except Exception as err:
            _LOGGER.error("Failed to set entity config: %s", err)

    async def handle_set_performance_profile(call):
        """Handle set_performance_profile service call."""
        profile_name = call.data["profile_name"]

        performance_manager = _get_performance_manager(hass)
        if not performance_manager:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            performance_manager.set_profile(profile_name)
            _LOGGER.info("Performance profile set to: %s", profile_name)
        except Exception as err:
            _LOGGER.error("Failed to set performance profile: %s", err)

    async def handle_get_health_report(call):
        """Handle get_health_report service call."""
        include_history = call.data.get("include_history", True)
        include_errors = call.data.get("include_errors", True)

        health_monitor = _get_health_monitor(hass)
        if not health_monitor:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            report = health_monitor.get_comprehensive_report(
                include_history=include_history,
                include_errors=include_errors,
            )
            _LOGGER.info("Health report generated: %s", report)
            return report

        except Exception as err:
            _LOGGER.error("Failed to generate health report: %s", err)

    async def handle_reset_statistics(call):
        """Handle reset_statistics service call."""
        confirm = call.data["confirm"]

        if not confirm:
            _LOGGER.warning("Statistics reset cancelled - confirmation required")
            return

        coordinator = _get_coordinator(hass)
        health_monitor = _get_health_monitor(hass)

        if not coordinator or not health_monitor:
            _LOGGER.error("No active Clarify integration found")
            return

        try:
            # Reset coordinator statistics
            coordinator.total_data_points_sent = 0
            coordinator.successful_sends = 0
            coordinator.failed_sends = 0

            # Reset health monitor statistics
            health_monitor.reset_statistics()

            _LOGGER.info("All statistics reset successfully")

        except Exception as err:
            _LOGGER.error("Failed to reset statistics: %s", err)

    # Register Phase 7 services

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_HISTORICAL,
        handle_sync_historical,
        schema=vol.Schema({
            vol.Required("entity_ids"): cv.entity_ids,
            vol.Required("start_time"): cv.string,
            vol.Optional("end_time"): cv.string,
            vol.Optional("batch_size", default=1000): cv.positive_int,
            vol.Optional("batch_delay", default=2.0): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=60.0)
            ),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FLUSH_BUFFER,
        handle_flush_buffer,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_TEMPLATE,
        handle_apply_template,
        schema=vol.Schema({
            vol.Required("template_name"): cv.string,
            vol.Required("entity_ids"): cv.entity_ids,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ENTITY_CONFIG,
        handle_set_entity_config,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
            vol.Optional("transmission_interval"): cv.positive_int,
            vol.Optional("aggregation_method"): cv.string,
            vol.Optional("aggregation_window"): cv.positive_int,
            vol.Optional("priority"): cv.string,
            vol.Optional("buffer_strategy"): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PERFORMANCE_PROFILE,
        handle_set_performance_profile,
        schema=vol.Schema({
            vol.Required("profile_name"): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_HEALTH_REPORT,
        handle_get_health_report,
        schema=vol.Schema({
            vol.Optional("include_history", default=True): cv.boolean,
            vol.Optional("include_errors", default=True): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_STATISTICS,
        handle_reset_statistics,
        schema=vol.Schema({
            vol.Required("confirm"): cv.boolean,
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


def _get_coordinator(hass: HomeAssistant) -> ClarifyDataCoordinator | None:
    """Get the coordinator from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_COORDINATOR in entry_data:
            return entry_data[ENTRY_DATA_COORDINATOR]

    return None


def _get_historical_sync(hass: HomeAssistant) -> HistoricalDataSync | None:
    """Get the historical sync manager from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_HISTORICAL_SYNC in entry_data:
            return entry_data[ENTRY_DATA_HISTORICAL_SYNC]

    return None


def _get_config_manager(hass: HomeAssistant) -> ConfigurationManager | None:
    """Get the configuration manager from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_CONFIG_MANAGER in entry_data:
            return entry_data[ENTRY_DATA_CONFIG_MANAGER]

    return None


def _get_performance_manager(hass: HomeAssistant) -> PerformanceManager | None:
    """Get the performance manager from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_PERFORMANCE_MANAGER in entry_data:
            return entry_data[ENTRY_DATA_PERFORMANCE_MANAGER]

    return None


def _get_health_monitor(hass: HomeAssistant) -> IntegrationHealthMonitor | None:
    """Get the health monitor from the first active integration instance."""
    if DOMAIN not in hass.data:
        return None

    for entry_data in hass.data[DOMAIN].values():
        if ENTRY_DATA_HEALTH_MONITOR in entry_data:
            return entry_data[ENTRY_DATA_HEALTH_MONITOR]

    return None
