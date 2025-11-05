"""Entity selection, classification, and filtering for Clarify Data Bridge.

This module provides comprehensive entity discovery and classification based on:
- Domain types
- Device classes
- Data types (numeric, binary, etc.)
- Metadata richness
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er, area_registry as ar
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)


class EntityCategory(Enum):
    """Categories of entities based on data type."""
    NUMERIC_SENSOR = "numeric_sensor"           # Pure numeric sensors
    BINARY_SENSOR = "binary_sensor"             # Binary sensors (on/off)
    MULTI_VALUE_SENSOR = "multi_value_sensor"   # Sensors with multiple numeric attributes
    CONTROL_DEVICE = "control_device"           # Switches, lights, etc. with state + attributes
    CLIMATE_DEVICE = "climate_device"           # Climate control with temperature data
    POWER_DEVICE = "power_device"               # Power monitoring devices
    ENVIRONMENTAL = "environmental"             # Weather, air quality, etc.
    OTHER = "other"                             # Other trackable entities


@dataclass
class EntityMetadata:
    """Comprehensive metadata for a Home Assistant entity."""

    # Core identity
    entity_id: str
    domain: str
    object_id: str

    # Display information
    friendly_name: str
    description: str | None = None

    # Classification
    device_class: str | None = None
    category: EntityCategory = EntityCategory.OTHER

    # Measurement info
    unit_of_measurement: str | None = None
    state_class: str | None = None

    # Device & location
    device_id: str | None = None
    device_name: str | None = None
    device_manufacturer: str | None = None
    device_model: str | None = None
    area_id: str | None = None
    area_name: str | None = None

    # Data characteristics
    has_numeric_state: bool = False
    numeric_attributes: list[str] | None = None

    # Additional attributes
    icon: str | None = None
    entity_category: str | None = None

    def to_labels(self) -> dict[str, list[str]]:
        """Convert metadata to Clarify labels format.

        Returns:
            Dictionary of label keys to value lists.
        """
        labels = {
            "source": ["Home Assistant"],
            "domain": [self.domain],
            "entity_id": [self.entity_id],
        }

        if self.device_class:
            labels["device_class"] = [self.device_class]

        if self.unit_of_measurement:
            labels["unit"] = [self.unit_of_measurement]

        if self.state_class:
            labels["state_class"] = [self.state_class]

        if self.area_name:
            labels["area"] = [self.area_name]

        if self.device_name:
            labels["device"] = [self.device_name]

        if self.device_manufacturer:
            labels["manufacturer"] = [self.device_manufacturer]

        if self.device_model:
            labels["model"] = [self.device_model]

        if self.category:
            labels["category"] = [self.category.value]

        return labels


class EntitySelector:
    """Select and classify Home Assistant entities for Clarify data collection.

    This class provides intelligent entity discovery with:
    - Comprehensive metadata extraction
    - Flexible filtering options
    - Entity categorization
    """

    # Device classes suitable for binary conversion (0/1)
    BINARY_DEVICE_CLASSES = {
        "battery_charging", "cold", "connectivity", "door", "garage_door",
        "gas", "heat", "light", "lock", "moisture", "motion", "moving",
        "occupancy", "opening", "plug", "power", "presence", "problem",
        "running", "safety", "smoke", "sound", "tamper", "update", "vibration",
        "window",
    }

    # Numeric attributes to extract from entities
    NUMERIC_ATTRIBUTES = [
        # Temperature
        "temperature", "current_temperature", "target_temperature",
        "target_temp_high", "target_temp_low",

        # Climate
        "humidity", "current_humidity", "target_humidity",
        "pressure", "wind_speed", "wind_bearing",

        # Power & Energy
        "power", "energy", "voltage", "current", "power_factor",
        "apparent_power", "reactive_power",

        # Battery
        "battery", "battery_level",

        # Light
        "brightness", "color_temp", "kelvin",

        # Media
        "volume_level", "media_position",

        # HVAC
        "fan_speed", "swing_mode",

        # Other
        "speed", "position", "tilt_position",
    ]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the entity selector.

        Args:
            hass: Home Assistant instance.
        """
        self.hass = hass
        self._entity_registry: er.EntityRegistry | None = None
        self._device_registry: dr.DeviceRegistry | None = None
        self._area_registry: ar.AreaRegistry | None = None

    async def async_setup(self) -> None:
        """Set up the entity selector with registries."""
        self._entity_registry = er.async_get(self.hass)
        self._device_registry = dr.async_get(self.hass)
        self._area_registry = ar.async_get(self.hass)

        _LOGGER.debug("EntitySelector initialized with registries")

    async def async_discover_entities(
        self,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_device_classes: list[str] | None = None,
        exclude_device_classes: list[str] | None = None,
        include_entity_ids: list[str] | None = None,
        exclude_entity_ids: list[str] | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[EntityMetadata]:
        """Discover and classify entities based on filters.

        Args:
            include_domains: List of domains to include (None = all trackable).
            exclude_domains: List of domains to exclude.
            include_device_classes: List of device classes to include.
            exclude_device_classes: List of device classes to exclude.
            include_entity_ids: Specific entity IDs to include.
            exclude_entity_ids: Specific entity IDs to exclude.
            include_patterns: Regex patterns for entity IDs to include.
            exclude_patterns: Regex patterns for entity IDs to exclude.

        Returns:
            List of EntityMetadata for discovered entities.
        """
        if not self._entity_registry:
            await self.async_setup()

        discovered_entities = []
        exclude_entity_set = set(exclude_entity_ids or [])
        include_entity_set = set(include_entity_ids or []) if include_entity_ids else None

        # Compile regex patterns
        include_regex = [re.compile(p) for p in (include_patterns or [])]
        exclude_regex = [re.compile(p) for p in (exclude_patterns or [])]

        _LOGGER.info("Starting entity discovery with filters: domains=%s",
                    include_domains)

        total_scanned = 0
        filtered_counts = {
            "domain": 0,
            "device_class": 0,
            "no_numeric": 0,
            "passed": 0,
        }

        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]
            total_scanned += 1

            # Skip excluded entities
            if entity_id in exclude_entity_set:
                continue

            # Check include list (if specified)
            if include_entity_set and entity_id not in include_entity_set:
                continue

            # Check domain filters
            if include_domains and domain not in include_domains:
                filtered_counts["domain"] += 1
                continue
            if exclude_domains and domain in exclude_domains:
                filtered_counts["domain"] += 1
                continue

            # Check regex patterns
            if include_regex and not any(p.match(entity_id) for p in include_regex):
                continue
            if exclude_regex and any(p.match(entity_id) for p in exclude_regex):
                continue

            # Extract metadata and classify
            metadata = await self.async_get_entity_metadata(entity_id, state)

            if not metadata:
                continue

            # Check device class filters
            if include_device_classes and metadata.device_class not in include_device_classes:
                filtered_counts["device_class"] += 1
                if "humidity" in entity_id:
                    _LOGGER.debug("Filtered %s by device_class: has=%s, required=%s",
                                 entity_id, metadata.device_class, include_device_classes)
                continue
            if exclude_device_classes and metadata.device_class in exclude_device_classes:
                filtered_counts["device_class"] += 1
                continue

            # Check if entity has trackable data
            if not (metadata.has_numeric_state or metadata.numeric_attributes):
                filtered_counts["no_numeric"] += 1
                continue

            filtered_counts["passed"] += 1
            discovered_entities.append(metadata)

        _LOGGER.info("Discovered %d trackable entities (scanned %d total)",
                    len(discovered_entities), total_scanned)
        _LOGGER.info("Filter breakdown: %s", filtered_counts)

        # Sort by entity_id for consistent ordering
        discovered_entities.sort(key=lambda x: x.entity_id)

        return discovered_entities

    async def async_get_entity_metadata(
        self,
        entity_id: str,
        state: State | None = None,
    ) -> EntityMetadata | None:
        """Extract comprehensive metadata for an entity.

        Args:
            entity_id: Entity ID to get metadata for.
            state: Optional state object (fetched if not provided).

        Returns:
            EntityMetadata object or None if entity not found/invalid.
        """
        if state is None:
            state = self.hass.states.get(entity_id)
            if not state:
                return None

        domain = entity_id.split(".")[0]
        object_id = entity_id.split(".", 1)[1]

        # Extract basic attributes
        friendly_name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        state_class = state.attributes.get("state_class")
        icon = state.attributes.get("icon")
        entity_category = state.attributes.get("entity_category")

        # Check for numeric state
        has_numeric_state = self._is_numeric(state.state)

        # Extract numeric attributes
        numeric_attributes = self._extract_numeric_attribute_names(state)

        # Determine category
        category = self._classify_entity(domain, device_class, has_numeric_state, numeric_attributes)

        # Get device and area information
        device_id = None
        device_name = None
        device_manufacturer = None
        device_model = None
        area_id = None
        area_name = None

        if self._entity_registry:
            entity_entry = self._entity_registry.async_get(entity_id)
            if entity_entry:
                device_id = entity_entry.device_id
                area_id = entity_entry.area_id

                # Get device info
                if device_id and self._device_registry:
                    device_entry = self._device_registry.async_get(device_id)
                    if device_entry:
                        device_name = device_entry.name_by_user or device_entry.name
                        device_manufacturer = device_entry.manufacturer
                        device_model = device_entry.model

                        # Use device area if entity doesn't have one
                        if not area_id:
                            area_id = device_entry.area_id

                # Get area name
                if area_id and self._area_registry:
                    area_entry = self._area_registry.async_get_area(area_id)
                    if area_entry:
                        area_name = area_entry.name

        # Build description
        description_parts = [f"Home Assistant {domain} entity"]
        if device_class:
            description_parts.append(f"Device class: {device_class}")
        if unit:
            description_parts.append(f"Unit: {unit}")
        description = " | ".join(description_parts)

        return EntityMetadata(
            entity_id=entity_id,
            domain=domain,
            object_id=object_id,
            friendly_name=friendly_name,
            description=description,
            device_class=device_class,
            category=category,
            unit_of_measurement=unit,
            state_class=state_class,
            device_id=device_id,
            device_name=device_name,
            device_manufacturer=device_manufacturer,
            device_model=device_model,
            area_id=area_id,
            area_name=area_name,
            has_numeric_state=has_numeric_state,
            numeric_attributes=numeric_attributes if numeric_attributes else None,
            icon=icon,
            entity_category=entity_category,
        )

    def _is_numeric(self, value: Any) -> bool:
        """Check if a value is numeric.

        Args:
            value: Value to check.

        Returns:
            True if value is numeric.
        """
        if value in ("unavailable", "unknown", None):
            return False

        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _extract_numeric_attribute_names(self, state: State) -> list[str]:
        """Extract names of attributes that have numeric values.

        Args:
            state: Entity state.

        Returns:
            List of attribute names with numeric values.
        """
        numeric_attrs = []

        for attr in self.NUMERIC_ATTRIBUTES:
            if attr in state.attributes and self._is_numeric(state.attributes[attr]):
                numeric_attrs.append(attr)

        return numeric_attrs

    def _classify_entity(
        self,
        domain: str,
        device_class: str | None,
        has_numeric_state: bool,
        numeric_attributes: list[str],
    ) -> EntityCategory:
        """Classify entity into a category.

        Args:
            domain: Entity domain.
            device_class: Device class.
            has_numeric_state: Whether entity has numeric state.
            numeric_attributes: List of numeric attribute names.

        Returns:
            EntityCategory for the entity.
        """
        # Binary sensor
        if domain == "binary_sensor":
            return EntityCategory.BINARY_SENSOR

        # Climate devices
        if domain == "climate":
            return EntityCategory.CLIMATE_DEVICE

        # Power monitoring
        if device_class in ("power", "energy", "voltage", "current"):
            return EntityCategory.POWER_DEVICE

        # Environmental sensors
        if device_class in ("temperature", "humidity", "pressure", "pm25", "pm10",
                           "carbon_dioxide", "aqi", "atmospheric_pressure"):
            return EntityCategory.ENVIRONMENTAL

        # Pure numeric sensor
        if domain == "sensor" and has_numeric_state and not numeric_attributes:
            return EntityCategory.NUMERIC_SENSOR

        # Multi-value sensor
        if has_numeric_state and numeric_attributes:
            return EntityCategory.MULTI_VALUE_SENSOR

        # Control devices
        if domain in ("light", "switch", "fan", "cover", "lock"):
            return EntityCategory.CONTROL_DEVICE

        return EntityCategory.OTHER

    def extract_numeric_values(
        self,
        state: State,
        metadata: EntityMetadata | None = None,
    ) -> dict[str, float]:
        """Extract all numeric values from entity state.

        Args:
            state: Entity state.
            metadata: Optional pre-computed metadata.

        Returns:
            Dictionary mapping attribute names to values.
            Empty string key for main state value.
        """
        values: dict[str, float] = {}

        # Extract main state if numeric
        if self._is_numeric(state.state):
            # Binary sensor special case: convert to 0/1
            if state.domain == "binary_sensor":
                values[""] = 1.0 if state.state == "on" else 0.0
            else:
                values[""] = float(state.state)

        # Extract numeric attributes
        if metadata and metadata.numeric_attributes:
            # Use pre-computed list
            for attr in metadata.numeric_attributes:
                if attr in state.attributes:
                    try:
                        values[attr] = float(state.attributes[attr])
                    except (ValueError, TypeError):
                        pass
        else:
            # Scan all known numeric attributes
            for attr in self.NUMERIC_ATTRIBUTES:
                if attr in state.attributes and self._is_numeric(state.attributes[attr]):
                    try:
                        values[attr] = float(state.attributes[attr])
                    except (ValueError, TypeError):
                        pass

        return values

    def group_entities_by_category(
        self,
        entities: list[EntityMetadata],
    ) -> dict[EntityCategory, list[EntityMetadata]]:
        """Group entities by category.

        Args:
            entities: List of entity metadata.

        Returns:
            Dictionary mapping categories to entity lists.
        """
        groups: dict[EntityCategory, list[EntityMetadata]] = {}

        for entity in entities:
            if entity.category not in groups:
                groups[entity.category] = []
            groups[entity.category].append(entity)

        return groups

    def group_entities_by_area(
        self,
        entities: list[EntityMetadata],
    ) -> dict[str, list[EntityMetadata]]:
        """Group entities by area.

        Args:
            entities: List of entity metadata.

        Returns:
            Dictionary mapping area names to entity lists.
        """
        groups: dict[str, list[EntityMetadata]] = {}

        for entity in entities:
            area = entity.area_name or "No Area"
            if area not in groups:
                groups[area] = []
            groups[area].append(entity)

        return groups
