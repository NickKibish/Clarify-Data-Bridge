"""Item manager for publishing Clarify items with automatic publishing strategies."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, State
from pyclarify.views.items import Item

from .clarify_client import ClarifyClient, ClarifyConnectionError
from .signal_manager import ClarifySignalManager
from .entity_selector import EntityMetadata
from .publishing_strategy import PublishingStrategyManager, PublishingStrategy, PublishingRule

_LOGGER = logging.getLogger(__name__)


class ClarifyItemManager:
    """Manager for publishing signals as items in Clarify.

    Items are the published version of signals that are visible
    to the entire organization in Clarify.

    Supports automatic publishing based on configurable strategies.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        signal_manager: ClarifySignalManager,
        publishing_strategy: PublishingStrategyManager | None = None,
        auto_publish: bool = False,
        default_visible: bool = True,
    ) -> None:
        """Initialize the item manager.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient instance for API communication.
            signal_manager: Signal manager to get signal IDs.
            publishing_strategy: Publishing strategy manager (optional).
            auto_publish: Automatically publish signals as items.
            default_visible: Default visibility for published items.
        """
        self.hass = hass
        self.client = client
        self.signal_manager = signal_manager
        self.publishing_strategy = publishing_strategy
        self.auto_publish = auto_publish
        self.default_visible = default_visible

        # Track published items: {signal_id: item_id}
        self._signal_to_item_id: dict[str, str] = {}

        # Track item metadata: {item_id: Item}
        self._item_metadata: dict[str, Item] = {}

        # Track auto-published entities
        self._auto_published: set[str] = set()

        _LOGGER.debug(
            "Initialized ClarifyItemManager (auto_publish=%s, default_visible=%s, strategy=%s)",
            auto_publish,
            default_visible,
            publishing_strategy.strategy.value if publishing_strategy else "none",
        )

    async def async_auto_publish_entities(
        self,
        entities: list[EntityMetadata],
    ) -> dict[str, str]:
        """Automatically publish entities based on publishing strategy.

        Args:
            entities: List of entity metadata to consider for publishing.

        Returns:
            Dictionary mapping entity_id to item_id for published entities.
        """
        if not self.auto_publish or not self.publishing_strategy:
            _LOGGER.debug("Auto-publish disabled or no strategy configured")
            return {}

        # Get entities to publish based on strategy
        to_publish = self.publishing_strategy.get_entities_to_publish(entities)

        if not to_publish:
            _LOGGER.info("No entities matched publishing strategy")
            return {}

        _LOGGER.info(
            "Auto-publishing %d entities based on strategy: %s",
            len(to_publish),
            self.publishing_strategy.strategy.value,
        )

        result = {}
        for entity_metadata, rule in to_publish:
            try:
                # Check if already published
                if self.is_published(entity_metadata.entity_id):
                    _LOGGER.debug("%s already published, skipping", entity_metadata.entity_id)
                    continue

                # Get visibility from strategy
                visible = self.publishing_strategy.get_visibility(entity_metadata, rule)

                # Get additional labels from strategy
                additional_labels = self.publishing_strategy.get_additional_labels(entity_metadata, rule)

                # Publish entity
                item_id = await self.async_publish_entity_with_metadata(
                    entity_metadata=entity_metadata,
                    visible=visible,
                    labels=additional_labels,
                )

                result[entity_metadata.entity_id] = item_id
                self._auto_published.add(entity_metadata.entity_id)

                _LOGGER.info(
                    "Auto-published %s (rule: %s, visible: %s)",
                    entity_metadata.entity_id,
                    rule.name if rule else "default",
                    visible,
                )

            except Exception as err:
                _LOGGER.error(
                    "Failed to auto-publish %s: %s",
                    entity_metadata.entity_id,
                    err,
                )
                continue

        _LOGGER.info(
            "Auto-published %d of %d entities",
            len(result),
            len(to_publish),
        )

        return result

    async def async_publish_entity_with_metadata(
        self,
        entity_metadata: EntityMetadata,
        visible: bool | None = None,
        labels: dict[str, list[str]] | None = None,
    ) -> str:
        """Publish entity using EntityMetadata for comprehensive labels.

        Args:
            entity_metadata: Entity metadata with comprehensive information.
            visible: Whether the item should be visible.
            labels: Additional labels for the item.

        Returns:
            Item ID from Clarify.
        """
        entity_id = entity_metadata.entity_id

        # Ensure signal exists first
        state = self.hass.states.get(entity_id)
        signal_id = await self.signal_manager.async_ensure_signal(entity_id, state)

        # Check if already published
        if signal_id in self._signal_to_item_id:
            item_id = self._signal_to_item_id[signal_id]
            _LOGGER.debug("Entity %s already published as item %s", entity_id, item_id)
            return item_id

        # Build item with enhanced metadata
        item = self._build_item_from_entity(
            entity_id=entity_id,
            state=state,
            visible=visible if visible is not None else self.default_visible,
            additional_labels=labels,
            entity_metadata=entity_metadata,
        )

        # Publish to Clarify
        try:
            _LOGGER.info("Publishing entity %s as Clarify item (signal_id: %s)", entity_id, signal_id)
            response = await self.client.async_publish_signals(
                signal_ids=[signal_id],
                items=[item],
                create_only=False,
            )

            # Extract item ID from response
            item_id = response.get("data", {}).get(signal_id, {}).get("id")
            if not item_id:
                raise ClarifyConnectionError(f"Failed to get item ID from response: {response}")

            # Store mapping
            self._signal_to_item_id[signal_id] = item_id
            self._item_metadata[item_id] = item

            _LOGGER.info("Successfully published %s as item %s", entity_id, item_id)
            return item_id

        except ClarifyConnectionError as err:
            _LOGGER.error("Failed to publish entity %s: %s", entity_id, err)
            raise

    async def async_publish_entity(
        self,
        entity_id: str,
        visible: bool | None = None,
        labels: dict[str, list[str]] | None = None,
        state: State | None = None,
    ) -> str:
        """Publish a Home Assistant entity as a Clarify item.

        Args:
            entity_id: Home Assistant entity ID.
            visible: Whether the item should be visible (default from config).
            labels: Additional labels for the item.
            state: Current state of the entity (optional).

        Returns:
            Item ID from Clarify.

        Raises:
            ClarifyConnectionError: If publishing fails.
        """
        # Ensure signal exists first
        signal_id = await self.signal_manager.async_ensure_signal(entity_id, state)

        # Check if already published
        if signal_id in self._signal_to_item_id:
            item_id = self._signal_to_item_id[signal_id]
            _LOGGER.debug("Entity %s already published as item %s", entity_id, item_id)
            return item_id

        # Get state if not provided
        if state is None:
            state = self.hass.states.get(entity_id)

        # Try to get enhanced metadata
        entity_metadata = self.signal_manager.get_entity_metadata(entity_id)

        # Build item from entity
        item = self._build_item_from_entity(
            entity_id,
            state,
            visible if visible is not None else self.default_visible,
            labels,
            entity_metadata,
        )

        # Publish to Clarify
        try:
            _LOGGER.info("Publishing entity %s as Clarify item (signal_id: %s)", entity_id, signal_id)
            response = await self.client.async_publish_signals(
                signal_ids=[signal_id],
                items=[item],
                create_only=False,
            )

            # Extract item ID from response
            item_id = response.get("data", {}).get(signal_id, {}).get("id")
            if not item_id:
                raise ClarifyConnectionError(f"Failed to get item ID from response: {response}")

            # Store mapping
            self._signal_to_item_id[signal_id] = item_id
            self._item_metadata[item_id] = item

            _LOGGER.info("Successfully published %s as item %s", entity_id, item_id)
            return item_id

        except ClarifyConnectionError as err:
            _LOGGER.error("Failed to publish entity %s: %s", entity_id, err)
            raise

    async def async_publish_multiple_entities(
        self,
        entity_ids: list[str],
        visible: bool | None = None,
        labels: dict[str, list[str]] | None = None,
    ) -> dict[str, str]:
        """Publish multiple entities as Clarify items.

        Args:
            entity_ids: List of Home Assistant entity IDs.
            visible: Whether items should be visible.
            labels: Additional labels for all items.

        Returns:
            Dictionary mapping entity_id to item_id.

        Raises:
            ClarifyConnectionError: If publishing fails.
        """
        result = {}

        for entity_id in entity_ids:
            try:
                item_id = await self.async_publish_entity(
                    entity_id=entity_id,
                    visible=visible,
                    labels=labels,
                )
                result[entity_id] = item_id
            except Exception as err:
                _LOGGER.error("Failed to publish entity %s: %s", entity_id, err)
                continue

        _LOGGER.info("Published %d of %d entities as items", len(result), len(entity_ids))
        return result

    async def async_publish_all_tracked(
        self,
        visible: bool | None = None,
        labels: dict[str, list[str]] | None = None,
    ) -> dict[str, str]:
        """Publish all tracked entities as items.

        Args:
            visible: Whether items should be visible.
            labels: Additional labels for all items.

        Returns:
            Dictionary mapping entity_id to item_id.
        """
        entity_ids = self.signal_manager.tracked_entities
        _LOGGER.info("Publishing %d tracked entities as items", len(entity_ids))

        return await self.async_publish_multiple_entities(
            entity_ids=entity_ids,
            visible=visible,
            labels=labels,
        )

    def _build_item_from_entity(
        self,
        entity_id: str,
        state: State | None,
        visible: bool,
        additional_labels: dict[str, list[str]] | None = None,
        entity_metadata: EntityMetadata | None = None,
    ) -> Item:
        """Build an Item from Home Assistant entity with enhanced metadata.

        Args:
            entity_id: Home Assistant entity ID.
            state: Current state of the entity.
            visible: Whether the item should be visible.
            additional_labels: Additional labels to add.
            entity_metadata: Enhanced entity metadata (optional).

        Returns:
            Item with comprehensive metadata.
        """
        # Use enhanced metadata if available
        if entity_metadata:
            name = entity_metadata.friendly_name
            description = entity_metadata.description or f"Home Assistant {entity_metadata.domain} entity"
            labels = entity_metadata.to_labels()
            # Add integration ID
            labels["integration"] = [self.signal_manager.integration_id]
        else:
            # Fall back to basic extraction
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            name = entity_id
            description = f"Home Assistant {domain} entity"

            if state is not None and state.attributes:
                name = state.attributes.get("friendly_name", entity_id)
                unit = state.attributes.get("unit_of_measurement")
                device_class = state.attributes.get("device_class")

                description_parts = [f"Home Assistant {domain} entity"]
                if device_class:
                    description_parts.append(f"Device class: {device_class}")
                if unit:
                    description_parts.append(f"Unit: {unit}")
                description = " | ".join(description_parts)

            labels = {
                "source": ["Home Assistant"],
                "domain": [domain],
                "entity_id": [entity_id],
                "integration": [self.signal_manager.integration_id],
            }

            if state is not None and state.attributes:
                if "unit_of_measurement" in state.attributes:
                    labels["unit"] = [state.attributes["unit_of_measurement"]]
                if "device_class" in state.attributes:
                    labels["device_class"] = [state.attributes["device_class"]]

        # Add additional labels
        if additional_labels:
            for key, values in additional_labels.items():
                if key in labels:
                    labels[key] = list(set(labels[key] + values))  # Merge and deduplicate
                else:
                    labels[key] = values

        # Create Item
        item = Item(
            name=name,
            description=description,
            labels=labels,
            visible=visible,
        )

        return item

    async def async_update_item_visibility(
        self,
        entity_id: str,
        visible: bool,
    ) -> None:
        """Update visibility of a published item.

        Args:
            entity_id: Home Assistant entity ID.
            visible: New visibility setting.

        Raises:
            ValueError: If entity is not published.
            ClarifyConnectionError: If update fails.
        """
        signal_id = self.signal_manager.get_input_id(entity_id)

        if signal_id not in self._signal_to_item_id:
            raise ValueError(f"Entity {entity_id} is not published as an item")

        # Get current item metadata
        item_id = self._signal_to_item_id[signal_id]
        current_item = self._item_metadata.get(item_id)

        if current_item is None:
            raise ValueError(f"No metadata found for item {item_id}")

        # Create updated item with new visibility
        updated_item = Item(
            name=current_item.name,
            description=current_item.description,
            labels=current_item.labels,
            visible=visible,
        )

        try:
            # Publish updated item
            await self.client.async_publish_signals(
                signal_ids=[signal_id],
                items=[updated_item],
                create_only=False,
            )

            # Update stored metadata
            self._item_metadata[item_id] = updated_item

            _LOGGER.info("Updated visibility for %s to %s", entity_id, visible)

        except ClarifyConnectionError as err:
            _LOGGER.error("Failed to update visibility for %s: %s", entity_id, err)
            raise

    def is_published(self, entity_id: str) -> bool:
        """Check if an entity has been published as an item.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            True if entity is published.
        """
        signal_id = self.signal_manager.get_input_id(entity_id)
        return signal_id in self._signal_to_item_id

    def is_auto_published(self, entity_id: str) -> bool:
        """Check if an entity was auto-published.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            True if entity was auto-published.
        """
        return entity_id in self._auto_published

    def get_item_id(self, entity_id: str) -> str | None:
        """Get item ID for an entity.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            Item ID or None if not published.
        """
        signal_id = self.signal_manager.get_input_id(entity_id)
        return self._signal_to_item_id.get(signal_id)

    @property
    def published_count(self) -> int:
        """Get number of published items."""
        return len(self._signal_to_item_id)

    @property
    def auto_published_count(self) -> int:
        """Get number of auto-published items."""
        return len(self._auto_published)

    @property
    def published_entities(self) -> list[str]:
        """Get list of published entity IDs."""
        published = []
        for entity_id in self.signal_manager.tracked_entities:
            if self.is_published(entity_id):
                published.append(entity_id)
        return published

    @property
    def auto_published_entities(self) -> list[str]:
        """Get list of auto-published entity IDs."""
        return list(self._auto_published)
