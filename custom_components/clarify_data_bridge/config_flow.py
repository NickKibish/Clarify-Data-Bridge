"""Config flow for Clarify Data Bridge integration."""
from __future__ import annotations

import logging
from typing import Any
from collections import defaultdict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er, area_registry as ar

from .clarify_client import (
    ClarifyClient,
    ClarifyAuthenticationError,
    ClarifyConnectionError,
)
from .entity_selector import EntitySelector, DataPriority, EntityCategory
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
    DEFAULT_NAME,
    DEFAULT_BATCH_INTERVAL,
    DEFAULT_MAX_BATCH_SIZE,
    SUPPORTED_DOMAINS,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)

# Step 1: Credentials
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
            hass=hass,
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

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._entity_selector: EntitySelector | None = None
        self._discovered_entities: list = []
        self._selected_entities: set[str] = set()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - credentials."""
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

                # Store credentials and move to selection method
                self._data = user_input
                self._data["title"] = info["title"]

                return await self.async_step_selection_method()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_selection_method(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user how they want to select entities."""
        if user_input is not None:
            method = user_input.get("selection_method")

            if method == "quick":
                # Quick setup with smart defaults
                return await self.async_step_quick_setup()
            elif method == "priority":
                # Select by priority level
                return await self.async_step_priority_selection()
            elif method == "domain":
                # Select by domain
                return await self.async_step_domain_selection()
            elif method == "device_class":
                # Select by device class
                return await self.async_step_device_class_selection()
            elif method == "manual":
                # Manual entity selection
                return await self.async_step_entity_selection()
            elif method == "advanced":
                # Advanced filtering with patterns
                return await self.async_step_advanced_filtering()

        schema = vol.Schema({
            vol.Required("selection_method", default="quick"): vol.In({
                "quick": "Quick Setup (Recommended - High priority entities)",
                "priority": "Select by Priority Level",
                "domain": "Select by Domain (sensor, climate, etc.)",
                "device_class": "Select by Device Class (temperature, power, etc.)",
                "manual": "Manual Entity Selection",
                "advanced": "Advanced Filtering (Patterns & Rules)",
            })
        })

        return self.async_show_form(
            step_id="selection_method",
            data_schema=schema,
            description_placeholders={
                "entities_available": str(len(self.hass.states.async_all()))
            }
        )

    async def async_step_quick_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Quick setup with smart defaults."""
        if user_input is not None:
            priority_level = user_input.get("priority_level", "HIGH")

            # Set default configuration
            self._data[CONF_MIN_PRIORITY] = priority_level
            self._data[CONF_INCLUDE_DOMAINS] = SUPPORTED_DOMAINS

            return await self.async_step_preview()

        schema = vol.Schema({
            vol.Required("priority_level", default="HIGH"): vol.In({
                "HIGH": "High Priority (Energy, Temperature, CO2, etc.)",
                "MEDIUM": "Medium Priority (High + Light, Motion, etc.)",
                "LOW": "All Entities (High + Medium + Binary Sensors)",
            })
        })

        return self.async_show_form(
            step_id="quick_setup",
            data_schema=schema,
        )

    async def async_step_priority_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entities by priority level."""
        if user_input is not None:
            self._data[CONF_MIN_PRIORITY] = user_input.get("min_priority", "LOW")
            self._data[CONF_INCLUDE_DOMAINS] = user_input.get("include_domains", SUPPORTED_DOMAINS)

            return await self.async_step_preview()

        # Initialize entity selector if needed
        if not self._entity_selector:
            self._entity_selector = EntitySelector(self.hass)
            await self._entity_selector.async_setup()

        # Get entity counts by priority
        all_entities = await self._entity_selector.async_discover_entities(
            include_domains=SUPPORTED_DOMAINS,
            min_priority=DataPriority.LOW
        )

        high_count = len([e for e in all_entities if e.priority == DataPriority.HIGH])
        medium_count = len([e for e in all_entities if e.priority == DataPriority.MEDIUM])
        low_count = len([e for e in all_entities if e.priority == DataPriority.LOW])

        schema = vol.Schema({
            vol.Required("min_priority", default="HIGH"): vol.In({
                "HIGH": f"High Priority Only ({high_count} entities)",
                "MEDIUM": f"Medium & High Priority ({high_count + medium_count} entities)",
                "LOW": f"All Priorities ({len(all_entities)} entities)",
            }),
            vol.Optional("include_domains", default=SUPPORTED_DOMAINS): cv.multi_select({
                domain: domain.replace("_", " ").title()
                for domain in SUPPORTED_DOMAINS
            }),
        })

        return self.async_show_form(
            step_id="priority_selection",
            data_schema=schema,
        )

    async def async_step_domain_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entities by domain."""
        if user_input is not None:
            self._data[CONF_INCLUDE_DOMAINS] = user_input.get("domains", [])
            self._data[CONF_MIN_PRIORITY] = "LOW"

            # Ask if they want to refine by priority
            if user_input.get("refine_priority"):
                return await self.async_step_priority_selection()

            return await self.async_step_preview()

        # Initialize entity selector
        if not self._entity_selector:
            self._entity_selector = EntitySelector(self.hass)
            await self._entity_selector.async_setup()

        # Count entities by domain
        domain_counts = defaultdict(int)
        for state in self.hass.states.async_all():
            domain = state.entity_id.split(".")[0]
            if domain in SUPPORTED_DOMAINS:
                domain_counts[domain] += 1

        domain_options = {
            domain: f"{domain.replace('_', ' ').title()} ({domain_counts.get(domain, 0)} entities)"
            for domain in SUPPORTED_DOMAINS
        }

        schema = vol.Schema({
            vol.Required("domains", default=["sensor"]): cv.multi_select(domain_options),
            vol.Optional("refine_priority", default=False): bool,
        })

        return self.async_show_form(
            step_id="domain_selection",
            data_schema=schema,
        )

    async def async_step_device_class_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entities by device class."""
        if user_input is not None:
            selected_classes = user_input.get("device_classes", [])
            self._data[CONF_INCLUDE_DEVICE_CLASSES] = selected_classes
            self._data[CONF_MIN_PRIORITY] = "LOW"

            return await self.async_step_preview()

        # Initialize entity selector
        if not self._entity_selector:
            self._entity_selector = EntitySelector(self.hass)
            await self._entity_selector.async_setup()

        # Get available device classes with counts
        device_class_counts = defaultdict(int)
        for state in self.hass.states.async_all():
            device_class = state.attributes.get("device_class")
            if device_class:
                device_class_counts[device_class] += 1

        # Sort by count (most common first)
        sorted_classes = sorted(
            device_class_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        device_class_options = {
            device_class: f"{device_class.replace('_', ' ').title()} ({count} entities)"
            for device_class, count in sorted_classes[:30]  # Limit to top 30
        }

        # Default selections for common high-value device classes
        default_classes = [
            "temperature", "humidity", "power", "energy",
            "voltage", "current", "carbon_dioxide"
        ]
        default_classes = [dc for dc in default_classes if dc in device_class_options]

        schema = vol.Schema({
            vol.Required("device_classes", default=default_classes): cv.multi_select(device_class_options),
        })

        return self.async_show_form(
            step_id="device_class_selection",
            data_schema=schema,
            description_placeholders={
                "device_class_count": str(len(device_class_options))
            }
        )

    async def async_step_entity_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual entity selection with search and filters."""
        if user_input is not None:
            if "entities" in user_input:
                selected = user_input["entities"]
                self._selected_entities = set(selected) if selected else set()

            # Check if user wants to add more filters
            if user_input.get("add_filters"):
                return await self.async_step_advanced_filtering()

            # Set configuration
            if self._selected_entities:
                # User manually selected specific entities
                self._data[CONF_INCLUDE_DOMAINS] = []
                self._data[CONF_EXCLUDE_ENTITIES] = [
                    e.entity_id for e in self._discovered_entities
                    if e.entity_id not in self._selected_entities
                ]

            return await self.async_step_preview()

        # Initialize and discover entities
        if not self._entity_selector:
            self._entity_selector = EntitySelector(self.hass)
            await self._entity_selector.async_setup()

        if not self._discovered_entities:
            self._discovered_entities = await self._entity_selector.async_discover_entities(
                include_domains=SUPPORTED_DOMAINS,
                min_priority=DataPriority.LOW
            )

        # Group entities by area for better UX
        entities_by_area = defaultdict(list)
        for entity in self._discovered_entities:
            area = entity.area_name or "No Area"
            entities_by_area[area].append(entity)

        # Create entity options (limit for performance)
        entity_options = {}
        for entity in self._discovered_entities[:200]:  # Limit to 200 for UI performance
            label = f"{entity.friendly_name}"
            if entity.device_class:
                label += f" ({entity.device_class})"
            if entity.area_name:
                label += f" - {entity.area_name}"
            entity_options[entity.entity_id] = label

        schema = vol.Schema({
            vol.Optional("entities", default=list(self._selected_entities)): cv.multi_select(entity_options),
            vol.Optional("add_filters", default=False): bool,
        })

        return self.async_show_form(
            step_id="entity_selection",
            data_schema=schema,
            description_placeholders={
                "entity_count": str(len(self._discovered_entities)),
                "showing": str(min(200, len(self._discovered_entities)))
            }
        )

    async def async_step_advanced_filtering(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Advanced filtering with patterns and exclusions."""
        if user_input is not None:
            # Store pattern filters
            if user_input.get("include_pattern"):
                self._data[CONF_INCLUDE_PATTERNS] = [
                    p.strip() for p in user_input["include_pattern"].split(",") if p.strip()
                ]

            if user_input.get("exclude_pattern"):
                self._data[CONF_EXCLUDE_PATTERNS] = [
                    p.strip() for p in user_input["exclude_pattern"].split(",") if p.strip()
                ]

            if user_input.get("exclude_entities"):
                self._data[CONF_EXCLUDE_ENTITIES] = [
                    e.strip() for e in user_input["exclude_entities"].split(",") if e.strip()
                ]

            # Priority if not set
            if CONF_MIN_PRIORITY not in self._data:
                self._data[CONF_MIN_PRIORITY] = user_input.get("min_priority", "LOW")

            return await self.async_step_preview()

        schema = vol.Schema({
            vol.Optional("include_pattern", default=""): str,
            vol.Optional("exclude_pattern", default=""): str,
            vol.Optional("exclude_entities", default=""): str,
            vol.Optional("min_priority", default="LOW"): vol.In({
                "HIGH": "High Priority",
                "MEDIUM": "Medium Priority",
                "LOW": "All Priorities",
            }),
        })

        return self.async_show_form(
            step_id="advanced_filtering",
            data_schema=schema,
        )

    async def async_step_preview(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Preview selected entities before finishing."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Add batch settings
                self._data[CONF_BATCH_INTERVAL] = DEFAULT_BATCH_INTERVAL
                self._data[CONF_MAX_BATCH_SIZE] = DEFAULT_MAX_BATCH_SIZE

                # Create entry
                title = self._data.pop("title")
                return self.async_create_entry(title=title, data=self._data)
            else:
                # Go back to selection method
                return await self.async_step_selection_method()

        # Discover entities with current filters
        if not self._entity_selector:
            self._entity_selector = EntitySelector(self.hass)
            await self._entity_selector.async_setup()

        # Build discovery parameters from stored data
        min_priority_str = self._data.get(CONF_MIN_PRIORITY, "LOW")
        try:
            min_priority = DataPriority[min_priority_str.upper()]
        except (KeyError, AttributeError):
            min_priority = DataPriority.LOW

        discovered = await self._entity_selector.async_discover_entities(
            include_domains=self._data.get(CONF_INCLUDE_DOMAINS, SUPPORTED_DOMAINS),
            include_device_classes=self._data.get(CONF_INCLUDE_DEVICE_CLASSES),
            exclude_device_classes=self._data.get(CONF_EXCLUDE_DEVICE_CLASSES),
            exclude_entity_ids=self._data.get(CONF_EXCLUDE_ENTITIES, []),
            min_priority=min_priority,
            include_patterns=self._data.get(CONF_INCLUDE_PATTERNS),
            exclude_patterns=self._data.get(CONF_EXCLUDE_PATTERNS),
        )

        # Generate preview summary
        priority_counts = defaultdict(int)
        category_counts = defaultdict(int)
        domain_counts = defaultdict(int)

        for entity in discovered:
            priority_counts[entity.priority.name] += 1
            category_counts[entity.category.value] += 1
            domain_counts[entity.domain] += 1

        # Sample entities to show
        sample_entities = [
            f"• {e.friendly_name} ({e.device_class or e.domain})"
            for e in discovered[:10]
        ]

        schema = vol.Schema({
            vol.Required("confirm", default=True): bool,
        })

        return self.async_show_form(
            step_id="preview",
            data_schema=schema,
            description_placeholders={
                "total_count": str(len(discovered)),
                "high_count": str(priority_counts.get("HIGH", 0)),
                "medium_count": str(priority_counts.get("MEDIUM", 0)),
                "low_count": str(priority_counts.get("LOW", 0)),
                "domains": ", ".join(f"{k}({v})" for k, v in sorted(domain_counts.items())),
                "categories": ", ".join(f"{k}({v})" for k, v in list(category_counts.items())[:5]),
                "samples": "\n".join(sample_entities),
            }
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Clarify Data Bridge."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._entity_selector: EntitySelector | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["batch_settings", "entity_filters", "advanced_filters"],
        )

    async def async_step_batch_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure batch settings."""
        if user_input is not None:
            # Update config entry data
            new_data = dict(self.config_entry.data)
            new_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current_batch_interval = self.config_entry.data.get(
            CONF_BATCH_INTERVAL, DEFAULT_BATCH_INTERVAL
        )
        current_max_batch_size = self.config_entry.data.get(
            CONF_MAX_BATCH_SIZE, DEFAULT_MAX_BATCH_SIZE
        )

        schema = vol.Schema({
            vol.Optional(
                CONF_BATCH_INTERVAL,
                default=current_batch_interval,
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            vol.Optional(
                CONF_MAX_BATCH_SIZE,
                default=current_max_batch_size,
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=1000)),
        })

        return self.async_show_form(
            step_id="batch_settings",
            data_schema=schema,
        )

    async def async_step_entity_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure entity filtering."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data[CONF_MIN_PRIORITY] = user_input.get("min_priority", "LOW")
            new_data[CONF_INCLUDE_DOMAINS] = user_input.get("include_domains", SUPPORTED_DOMAINS)
            new_data[CONF_INCLUDE_DEVICE_CLASSES] = user_input.get("include_device_classes", [])

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current_priority = self.config_entry.data.get(CONF_MIN_PRIORITY, "LOW")
        current_domains = self.config_entry.data.get(CONF_INCLUDE_DOMAINS, SUPPORTED_DOMAINS)
        current_device_classes = self.config_entry.data.get(CONF_INCLUDE_DEVICE_CLASSES, [])

        # Get available device classes
        device_class_counts = defaultdict(int)
        for state in self.hass.states.async_all():
            device_class = state.attributes.get("device_class")
            if device_class:
                device_class_counts[device_class] += 1

        device_class_options = {
            dc: f"{dc.replace('_', ' ').title()} ({count})"
            for dc, count in sorted(device_class_counts.items())[:30]
        }

        schema = vol.Schema({
            vol.Optional("min_priority", default=current_priority): vol.In({
                "HIGH": "High Priority",
                "MEDIUM": "Medium Priority",
                "LOW": "All Priorities",
            }),
            vol.Optional("include_domains", default=current_domains): cv.multi_select({
                domain: domain.replace("_", " ").title()
                for domain in SUPPORTED_DOMAINS
            }),
            vol.Optional("include_device_classes", default=current_device_classes): cv.multi_select(device_class_options),
        })

        return self.async_show_form(
            step_id="entity_filters",
            data_schema=schema,
        )

    async def async_step_advanced_filters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure advanced filtering."""
        if user_input is not None:
            new_data = dict(self.config_entry.data)

            if user_input.get("include_patterns"):
                new_data[CONF_INCLUDE_PATTERNS] = [
                    p.strip() for p in user_input["include_patterns"].split(",") if p.strip()
                ]
            else:
                new_data.pop(CONF_INCLUDE_PATTERNS, None)

            if user_input.get("exclude_patterns"):
                new_data[CONF_EXCLUDE_PATTERNS] = [
                    p.strip() for p in user_input["exclude_patterns"].split(",") if p.strip()
                ]
            else:
                new_data.pop(CONF_EXCLUDE_PATTERNS, None)

            if user_input.get("exclude_entities"):
                new_data[CONF_EXCLUDE_ENTITIES] = [
                    e.strip() for e in user_input["exclude_entities"].split(",") if e.strip()
                ]
            else:
                new_data.pop(CONF_EXCLUDE_ENTITIES, None)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current_include_patterns = self.config_entry.data.get(CONF_INCLUDE_PATTERNS, [])
        current_exclude_patterns = self.config_entry.data.get(CONF_EXCLUDE_PATTERNS, [])
        current_exclude_entities = self.config_entry.data.get(CONF_EXCLUDE_ENTITIES, [])

        schema = vol.Schema({
            vol.Optional(
                "include_patterns",
                default=", ".join(current_include_patterns)
            ): str,
            vol.Optional(
                "exclude_patterns",
                default=", ".join(current_exclude_patterns)
            ): str,
            vol.Optional(
                "exclude_entities",
                default=", ".join(current_exclude_entities)
            ): str,
        })

        return self.async_show_form(
            step_id="advanced_filters",
            data_schema=schema,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
