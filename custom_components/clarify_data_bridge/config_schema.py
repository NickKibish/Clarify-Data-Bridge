"""Configuration schema and templates for Clarify Data Bridge."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)


class AggregationMethod(Enum):
    """Data aggregation methods."""

    NONE = "none"  # No aggregation, send all points
    AVERAGE = "average"  # Average over interval
    MIN = "min"  # Minimum value
    MAX = "max"  # Maximum value
    SUM = "sum"  # Sum of values
    FIRST = "first"  # First value in interval
    LAST = "last"  # Last value in interval


@dataclass
class EntityConfig:
    """Per-entity configuration."""

    entity_id: str
    transmission_interval: int | None = None  # Override default interval (seconds)
    aggregation_method: AggregationMethod = AggregationMethod.NONE
    aggregation_window: int | None = None  # Window in seconds
    custom_labels: dict[str, list[str]] = field(default_factory=dict)
    custom_name: str | None = None
    enabled: bool = True
    priority_override: str | None = None  # Override detected priority


@dataclass
class ConfigTemplate:
    """Configuration template for common sensor types."""

    name: str
    description: str
    domains: list[str] = field(default_factory=list)
    device_classes: list[str] = field(default_factory=list)
    transmission_interval: int = 300
    aggregation_method: AggregationMethod = AggregationMethod.NONE
    aggregation_window: int | None = None
    default_labels: dict[str, list[str]] = field(default_factory=dict)
    buffer_strategy: str = "hybrid"
    priority: str = "medium"


# Pre-defined configuration templates
ENERGY_MONITORING_TEMPLATE = ConfigTemplate(
    name="Energy Monitoring",
    description="Optimized for energy and power sensors with frequent updates",
    domains=["sensor"],
    device_classes=["energy", "power", "voltage", "current"],
    transmission_interval=60,  # 1 minute
    aggregation_method=AggregationMethod.AVERAGE,
    aggregation_window=60,
    default_labels={"monitoring_type": ["energy"]},
    buffer_strategy="priority",
    priority="high",
)

ENVIRONMENTAL_MONITORING_TEMPLATE = ConfigTemplate(
    name="Environmental Monitoring",
    description="For temperature, humidity, and air quality sensors",
    domains=["sensor"],
    device_classes=["temperature", "humidity", "carbon_dioxide", "pm25", "aqi"],
    transmission_interval=300,  # 5 minutes
    aggregation_method=AggregationMethod.AVERAGE,
    aggregation_window=300,
    default_labels={"monitoring_type": ["environmental"]},
    buffer_strategy="hybrid",
    priority="high",
)

HVAC_MONITORING_TEMPLATE = ConfigTemplate(
    name="HVAC Monitoring",
    description="For climate control and HVAC systems",
    domains=["climate"],
    device_classes=[],
    transmission_interval=300,  # 5 minutes
    aggregation_method=AggregationMethod.LAST,
    aggregation_window=None,
    default_labels={"monitoring_type": ["hvac"], "system": ["climate"]},
    buffer_strategy="hybrid",
    priority="medium",
)

BINARY_SENSOR_TEMPLATE = ConfigTemplate(
    name="Binary Sensors",
    description="For motion, door, window sensors (converted to 0/1)",
    domains=["binary_sensor"],
    device_classes=["motion", "door", "window", "occupancy"],
    transmission_interval=60,  # 1 minute
    aggregation_method=AggregationMethod.NONE,  # Don't aggregate state changes
    aggregation_window=None,
    default_labels={"monitoring_type": ["binary"]},
    buffer_strategy="size",
    priority="low",
)

MOTION_ANALYTICS_TEMPLATE = ConfigTemplate(
    name="Motion Analytics",
    description="Optimized for motion sensor analytics with aggregation",
    domains=["binary_sensor"],
    device_classes=["motion", "occupancy"],
    transmission_interval=300,  # 5 minutes
    aggregation_method=AggregationMethod.SUM,  # Count activations
    aggregation_window=300,
    default_labels={"monitoring_type": ["motion_analytics"]},
    buffer_strategy="time",
    priority="low",
)

LIGHTING_MONITORING_TEMPLATE = ConfigTemplate(
    name="Lighting Monitoring",
    description="For light sensors and brightness tracking",
    domains=["light", "sensor"],
    device_classes=["illuminance", "brightness"],
    transmission_interval=600,  # 10 minutes
    aggregation_method=AggregationMethod.AVERAGE,
    aggregation_window=600,
    default_labels={"monitoring_type": ["lighting"]},
    buffer_strategy="hybrid",
    priority="low",
)

COMPREHENSIVE_MONITORING_TEMPLATE = ConfigTemplate(
    name="Comprehensive Monitoring",
    description="Balanced configuration for all sensor types",
    domains=["sensor", "binary_sensor", "climate"],
    device_classes=[],
    transmission_interval=300,  # 5 minutes
    aggregation_method=AggregationMethod.NONE,
    aggregation_window=None,
    default_labels={"monitoring_type": ["comprehensive"]},
    buffer_strategy="hybrid",
    priority="medium",
)

REAL_TIME_CRITICAL_TEMPLATE = ConfigTemplate(
    name="Real-Time Critical",
    description="Minimal latency for critical sensors",
    domains=["sensor"],
    device_classes=["energy", "power", "carbon_dioxide", "smoke", "gas"],
    transmission_interval=30,  # 30 seconds
    aggregation_method=AggregationMethod.NONE,
    aggregation_window=None,
    default_labels={"monitoring_type": ["critical"], "real_time": ["yes"]},
    buffer_strategy="priority",
    priority="high",
)

# All available templates
AVAILABLE_TEMPLATES = {
    "energy_monitoring": ENERGY_MONITORING_TEMPLATE,
    "environmental_monitoring": ENVIRONMENTAL_MONITORING_TEMPLATE,
    "hvac_monitoring": HVAC_MONITORING_TEMPLATE,
    "binary_sensor": BINARY_SENSOR_TEMPLATE,
    "motion_analytics": MOTION_ANALYTICS_TEMPLATE,
    "lighting_monitoring": LIGHTING_MONITORING_TEMPLATE,
    "comprehensive": COMPREHENSIVE_MONITORING_TEMPLATE,
    "real_time_critical": REAL_TIME_CRITICAL_TEMPLATE,
}


class ConfigurationManager:
    """Manages configuration schema and templates."""

    def __init__(self) -> None:
        """Initialize configuration manager."""
        self._entity_configs: dict[str, EntityConfig] = {}
        self._applied_templates: list[str] = []

        _LOGGER.debug("Initialized ConfigurationManager")

    def apply_template(
        self,
        template_name: str,
        entity_ids: list[str] | None = None,
    ) -> int:
        """Apply configuration template to entities.

        Args:
            template_name: Name of template to apply.
            entity_ids: List of entity IDs to apply template to.
                       If None, applies based on template's domain/device_class filters.

        Returns:
            Number of entities configured.
        """
        if template_name not in AVAILABLE_TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = AVAILABLE_TEMPLATES[template_name]

        if entity_ids is None:
            _LOGGER.warning(
                "Template application requires entity_ids list or discovery logic"
            )
            return 0

        configured_count = 0

        for entity_id in entity_ids:
            config = EntityConfig(
                entity_id=entity_id,
                transmission_interval=template.transmission_interval,
                aggregation_method=template.aggregation_method,
                aggregation_window=template.aggregation_window,
                custom_labels=template.default_labels.copy(),
                enabled=True,
                priority_override=template.priority,
            )

            self._entity_configs[entity_id] = config
            configured_count += 1

        self._applied_templates.append(template_name)

        _LOGGER.info(
            "Applied template '%s' to %d entities",
            template_name,
            configured_count,
        )

        return configured_count

    def set_entity_config(
        self,
        entity_id: str,
        config: EntityConfig | dict[str, Any],
    ) -> None:
        """Set configuration for a specific entity.

        Args:
            entity_id: Entity ID to configure.
            config: EntityConfig object or dictionary.
        """
        if isinstance(config, dict):
            # Convert dict to EntityConfig
            aggregation_method = config.get("aggregation_method", "none")
            if isinstance(aggregation_method, str):
                aggregation_method = AggregationMethod(aggregation_method)

            config = EntityConfig(
                entity_id=entity_id,
                transmission_interval=config.get("transmission_interval"),
                aggregation_method=aggregation_method,
                aggregation_window=config.get("aggregation_window"),
                custom_labels=config.get("custom_labels", {}),
                custom_name=config.get("custom_name"),
                enabled=config.get("enabled", True),
                priority_override=config.get("priority_override"),
            )

        self._entity_configs[entity_id] = config

        _LOGGER.debug("Set configuration for entity %s", entity_id)

    def get_entity_config(self, entity_id: str) -> EntityConfig | None:
        """Get configuration for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            EntityConfig or None if not configured.
        """
        return self._entity_configs.get(entity_id)

    def get_transmission_interval(
        self,
        entity_id: str,
        default: int = 300,
    ) -> int:
        """Get transmission interval for entity.

        Args:
            entity_id: Entity ID.
            default: Default interval if not configured.

        Returns:
            Transmission interval in seconds.
        """
        config = self.get_entity_config(entity_id)
        if config and config.transmission_interval is not None:
            return config.transmission_interval
        return default

    def get_aggregation_config(
        self,
        entity_id: str,
    ) -> tuple[AggregationMethod, int | None]:
        """Get aggregation configuration for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Tuple of (aggregation_method, aggregation_window).
        """
        config = self.get_entity_config(entity_id)
        if config:
            return config.aggregation_method, config.aggregation_window
        return AggregationMethod.NONE, None

    def get_custom_labels(
        self,
        entity_id: str,
    ) -> dict[str, list[str]]:
        """Get custom labels for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Dictionary of custom labels.
        """
        config = self.get_entity_config(entity_id)
        if config:
            return config.custom_labels.copy()
        return {}

    def is_entity_enabled(self, entity_id: str) -> bool:
        """Check if entity is enabled.

        Args:
            entity_id: Entity ID.

        Returns:
            True if enabled (default True if not configured).
        """
        config = self.get_entity_config(entity_id)
        if config:
            return config.enabled
        return True

    def get_all_entity_configs(self) -> dict[str, EntityConfig]:
        """Get all entity configurations.

        Returns:
            Dictionary mapping entity_id to EntityConfig.
        """
        return self._entity_configs.copy()

    def get_applied_templates(self) -> list[str]:
        """Get list of applied template names.

        Returns:
            List of template names.
        """
        return self._applied_templates.copy()

    def clear_entity_config(self, entity_id: str) -> bool:
        """Clear configuration for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            True if config was removed.
        """
        if entity_id in self._entity_configs:
            del self._entity_configs[entity_id]
            _LOGGER.debug("Cleared configuration for entity %s", entity_id)
            return True
        return False

    def export_config(self) -> dict[str, Any]:
        """Export configuration to dictionary.

        Returns:
            Dictionary representation of configuration.
        """
        return {
            "applied_templates": self._applied_templates,
            "entity_configs": {
                entity_id: {
                    "transmission_interval": config.transmission_interval,
                    "aggregation_method": config.aggregation_method.value,
                    "aggregation_window": config.aggregation_window,
                    "custom_labels": config.custom_labels,
                    "custom_name": config.custom_name,
                    "enabled": config.enabled,
                    "priority_override": config.priority_override,
                }
                for entity_id, config in self._entity_configs.items()
            },
        }


# Voluptuous schema for YAML configuration validation
ENTITY_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional("transmission_interval"): vol.All(int, vol.Range(min=30, max=3600)),
        vol.Optional("aggregation_method"): vol.In(
            ["none", "average", "min", "max", "sum", "first", "last"]
        ),
        vol.Optional("aggregation_window"): vol.All(int, vol.Range(min=60, max=3600)),
        vol.Optional("custom_labels"): dict,
        vol.Optional("custom_name"): cv.string,
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("priority_override"): vol.In(["high", "medium", "low"]),
    }
)

TEMPLATE_APPLICATION_SCHEMA = vol.Schema(
    {
        vol.Required("template"): vol.In(list(AVAILABLE_TEMPLATES.keys())),
        vol.Optional("entity_ids"): vol.All(cv.ensure_list, [cv.entity_id]),
    }
)


def get_template_options() -> list[tuple[str, str]]:
    """Get list of available templates for UI.

    Returns:
        List of (template_key, template_description) tuples.
    """
    return [
        (key, template.description)
        for key, template in AVAILABLE_TEMPLATES.items()
    ]


def validate_entity_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate entity configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Validated configuration.

    Raises:
        vol.Invalid: If configuration is invalid.
    """
    return ENTITY_CONFIG_SCHEMA(config)


def validate_template_application(config: dict[str, Any]) -> dict[str, Any]:
    """Validate template application configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Validated configuration.

    Raises:
        vol.Invalid: If configuration is invalid.
    """
    return TEMPLATE_APPLICATION_SCHEMA(config)
