"""Publishing strategy system for intelligent item management in Clarify.

This module provides strategies for automatically publishing signals as items
based on various criteria such as priority, device class, domain, and custom rules.
"""
from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Callable

from homeassistant.core import HomeAssistant

from .entity_selector import EntityMetadata, DataPriority, EntityCategory

_LOGGER = logging.getLogger(__name__)


class PublishingStrategy(Enum):
    """Publishing strategies for Clarify items."""

    MANUAL = "manual"                    # No automatic publishing
    ALL = "all"                          # Publish all tracked entities
    HIGH_PRIORITY = "high_priority"      # Publish only high priority entities
    MEDIUM_PLUS = "medium_plus"          # Publish medium and high priority
    BY_CATEGORY = "by_category"          # Publish specific categories
    BY_DEVICE_CLASS = "by_device_class"  # Publish specific device classes
    BY_DOMAIN = "by_domain"              # Publish specific domains
    CUSTOM = "custom"                    # Custom rule-based publishing


class PublishingVisibility(Enum):
    """Visibility settings for published items."""

    VISIBLE = "visible"                  # Item visible to organization
    HIDDEN = "hidden"                    # Item hidden from main view
    PRIORITY_BASED = "priority_based"    # Visibility based on priority


@dataclass
class PublishingRule:
    """Rule for automatic publishing of entities."""

    # Rule identification
    name: str
    description: str

    # Filtering criteria
    min_priority: DataPriority | None = None
    max_priority: DataPriority | None = None
    categories: list[EntityCategory] | None = None
    device_classes: list[str] | None = None
    domains: list[str] | None = None
    entity_pattern: str | None = None  # Regex pattern

    # Publishing settings
    visible: bool = True
    additional_labels: dict[str, list[str]] | None = None

    # Custom filter function
    custom_filter: Callable[[EntityMetadata], bool] | None = None

    def matches(self, entity: EntityMetadata) -> bool:
        """Check if entity matches this rule.

        Args:
            entity: Entity metadata to check.

        Returns:
            True if entity matches all criteria.
        """
        # Priority check
        if self.min_priority and entity.priority.value > self.min_priority.value:
            return False
        if self.max_priority and entity.priority.value < self.max_priority.value:
            return False

        # Category check
        if self.categories and entity.category not in self.categories:
            return False

        # Device class check
        if self.device_classes:
            if not entity.device_class or entity.device_class not in self.device_classes:
                return False

        # Domain check
        if self.domains and entity.domain not in self.domains:
            return False

        # Pattern check
        if self.entity_pattern:
            import re
            if not re.match(self.entity_pattern, entity.entity_id):
                return False

        # Custom filter
        if self.custom_filter and not self.custom_filter(entity):
            return False

        return True


class PublishingStrategyManager:
    """Manager for automatic publishing strategies."""

    # Pre-defined publishing strategies
    STRATEGY_RULES = {
        PublishingStrategy.MANUAL: [],

        PublishingStrategy.ALL: [
            PublishingRule(
                name="Publish All",
                description="Publish all tracked entities",
                visible=True,
            )
        ],

        PublishingStrategy.HIGH_PRIORITY: [
            PublishingRule(
                name="High Priority Only",
                description="Publish only high priority entities (energy, temperature, CO2, etc.)",
                min_priority=DataPriority.HIGH,
                max_priority=DataPriority.HIGH,
                visible=True,
            )
        ],

        PublishingStrategy.MEDIUM_PLUS: [
            PublishingRule(
                name="Medium and High Priority",
                description="Publish medium and high priority entities",
                min_priority=DataPriority.HIGH,
                visible=True,
            )
        ],

        PublishingStrategy.BY_CATEGORY: [
            PublishingRule(
                name="Power Devices",
                description="Power monitoring devices",
                categories=[EntityCategory.POWER_DEVICE],
                visible=True,
            ),
            PublishingRule(
                name="Environmental Sensors",
                description="Environmental and climate sensors",
                categories=[EntityCategory.ENVIRONMENTAL, EntityCategory.CLIMATE_DEVICE],
                visible=True,
            ),
        ],
    }

    def __init__(
        self,
        hass: HomeAssistant,
        strategy: PublishingStrategy = PublishingStrategy.MANUAL,
        custom_rules: list[PublishingRule] | None = None,
    ) -> None:
        """Initialize the publishing strategy manager.

        Args:
            hass: Home Assistant instance.
            strategy: Publishing strategy to use.
            custom_rules: Custom publishing rules (for CUSTOM strategy).
        """
        self.hass = hass
        self.strategy = strategy
        self.custom_rules = custom_rules or []

        # Get rules for selected strategy
        self.rules = self._get_rules_for_strategy()

        _LOGGER.info(
            "Initialized PublishingStrategyManager with strategy: %s (%d rules)",
            strategy.value,
            len(self.rules),
        )

    def _get_rules_for_strategy(self) -> list[PublishingRule]:
        """Get publishing rules for the selected strategy.

        Returns:
            List of publishing rules.
        """
        if self.strategy == PublishingStrategy.CUSTOM:
            return self.custom_rules

        return self.STRATEGY_RULES.get(self.strategy, [])

    def should_publish(self, entity: EntityMetadata) -> tuple[bool, PublishingRule | None]:
        """Determine if an entity should be published.

        Args:
            entity: Entity metadata to check.

        Returns:
            Tuple of (should_publish, matching_rule).
        """
        # Manual strategy - never auto-publish
        if self.strategy == PublishingStrategy.MANUAL:
            return False, None

        # Check each rule
        for rule in self.rules:
            if rule.matches(entity):
                return True, rule

        return False, None

    def get_entities_to_publish(
        self,
        entities: list[EntityMetadata],
    ) -> list[tuple[EntityMetadata, PublishingRule]]:
        """Get entities that should be published based on strategy.

        Args:
            entities: List of entity metadata to check.

        Returns:
            List of (entity, rule) tuples for entities to publish.
        """
        to_publish = []

        for entity in entities:
            should_pub, rule = self.should_publish(entity)
            if should_pub and rule:
                to_publish.append((entity, rule))

        _LOGGER.info(
            "Publishing strategy %s matched %d of %d entities",
            self.strategy.value,
            len(to_publish),
            len(entities),
        )

        return to_publish

    def get_visibility(
        self,
        entity: EntityMetadata,
        rule: PublishingRule | None = None,
    ) -> bool:
        """Determine visibility for an entity.

        Args:
            entity: Entity metadata.
            rule: Publishing rule that matched (if any).

        Returns:
            Visibility setting for the item.
        """
        # Use rule visibility if available
        if rule:
            return rule.visible

        # Default based on priority
        return entity.priority == DataPriority.HIGH

    def get_additional_labels(
        self,
        entity: EntityMetadata,
        rule: PublishingRule | None = None,
    ) -> dict[str, list[str]]:
        """Get additional labels for an entity.

        Args:
            entity: Entity metadata.
            rule: Publishing rule that matched (if any).

        Returns:
            Additional labels to add to the item.
        """
        labels = {}

        # Add rule-specific labels
        if rule and rule.additional_labels:
            labels.update(rule.additional_labels)

        # Add strategy label
        labels["publishing_strategy"] = [self.strategy.value]

        if rule:
            labels["publishing_rule"] = [rule.name]

        return labels

    @staticmethod
    def create_custom_rule(
        name: str,
        description: str,
        **kwargs,
    ) -> PublishingRule:
        """Create a custom publishing rule.

        Args:
            name: Rule name.
            description: Rule description.
            **kwargs: Additional rule parameters.

        Returns:
            PublishingRule instance.
        """
        return PublishingRule(
            name=name,
            description=description,
            **kwargs,
        )

    @staticmethod
    def create_priority_rule(
        min_priority: DataPriority,
        max_priority: DataPriority | None = None,
        visible: bool = True,
    ) -> PublishingRule:
        """Create a priority-based publishing rule.

        Args:
            min_priority: Minimum priority level.
            max_priority: Maximum priority level (optional).
            visible: Item visibility.

        Returns:
            PublishingRule instance.
        """
        max_priority = max_priority or min_priority

        return PublishingRule(
            name=f"Priority {min_priority.name}",
            description=f"Publish {min_priority.name.lower()} priority entities",
            min_priority=min_priority,
            max_priority=max_priority,
            visible=visible,
        )

    @staticmethod
    def create_device_class_rule(
        device_classes: list[str],
        visible: bool = True,
    ) -> PublishingRule:
        """Create a device class-based publishing rule.

        Args:
            device_classes: List of device classes to publish.
            visible: Item visibility.

        Returns:
            PublishingRule instance.
        """
        return PublishingRule(
            name=f"Device Classes: {', '.join(device_classes[:3])}{'...' if len(device_classes) > 3 else ''}",
            description=f"Publish entities with device classes: {', '.join(device_classes)}",
            device_classes=device_classes,
            visible=visible,
        )

    @staticmethod
    def create_category_rule(
        categories: list[EntityCategory],
        visible: bool = True,
    ) -> PublishingRule:
        """Create a category-based publishing rule.

        Args:
            categories: List of entity categories to publish.
            visible: Item visibility.

        Returns:
            PublishingRule instance.
        """
        category_names = [c.value for c in categories]

        return PublishingRule(
            name=f"Categories: {', '.join(category_names[:2])}{'...' if len(category_names) > 2 else ''}",
            description=f"Publish entities in categories: {', '.join(category_names)}",
            categories=categories,
            visible=visible,
        )

    def update_strategy(
        self,
        strategy: PublishingStrategy,
        custom_rules: list[PublishingRule] | None = None,
    ) -> None:
        """Update the publishing strategy.

        Args:
            strategy: New publishing strategy.
            custom_rules: New custom rules (for CUSTOM strategy).
        """
        self.strategy = strategy
        if custom_rules:
            self.custom_rules = custom_rules

        self.rules = self._get_rules_for_strategy()

        _LOGGER.info(
            "Updated publishing strategy to: %s (%d rules)",
            strategy.value,
            len(self.rules),
        )

    def get_strategy_summary(self) -> dict[str, any]:
        """Get summary of current publishing strategy.

        Returns:
            Dictionary with strategy information.
        """
        return {
            "strategy": self.strategy.value,
            "rule_count": len(self.rules),
            "rules": [
                {
                    "name": rule.name,
                    "description": rule.description,
                    "visible": rule.visible,
                }
                for rule in self.rules
            ],
        }


# Pre-defined publishing rule factories
def create_energy_monitoring_rules() -> list[PublishingRule]:
    """Create rules for energy monitoring setup.

    Returns:
        List of publishing rules for energy monitoring.
    """
    return [
        PublishingRule(
            name="Power and Energy Sensors",
            description="All power and energy monitoring sensors",
            device_classes=["power", "energy", "voltage", "current", "apparent_power", "reactive_power"],
            visible=True,
            additional_labels={"monitoring_type": ["energy"]},
        ),
    ]


def create_climate_monitoring_rules() -> list[PublishingRule]:
    """Create rules for climate monitoring setup.

    Returns:
        List of publishing rules for climate monitoring.
    """
    return [
        PublishingRule(
            name="Climate Sensors",
            description="Temperature, humidity, and air quality sensors",
            device_classes=["temperature", "humidity", "carbon_dioxide", "pm25", "pm10", "aqi"],
            visible=True,
            additional_labels={"monitoring_type": ["climate"]},
        ),
    ]


def create_comprehensive_monitoring_rules() -> list[PublishingRule]:
    """Create rules for comprehensive home monitoring.

    Returns:
        List of publishing rules for comprehensive monitoring.
    """
    return [
        PublishingRule(
            name="High Priority Sensors",
            description="All high priority sensors visible",
            min_priority=DataPriority.HIGH,
            max_priority=DataPriority.HIGH,
            visible=True,
        ),
        PublishingRule(
            name="Medium Priority Sensors",
            description="Medium priority sensors hidden by default",
            min_priority=DataPriority.MEDIUM,
            max_priority=DataPriority.MEDIUM,
            visible=False,
        ),
    ]
