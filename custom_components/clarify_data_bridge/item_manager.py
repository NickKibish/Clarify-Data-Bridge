"""Item manager for publishing Clarify items."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, State
from pyclarify.views.items import Item

from .clarify_client import ClarifyClient, ClarifyConnectionError
from .signal_manager import ClarifySignalManager

_LOGGER = logging.getLogger(__name__)


class ClarifyItemManager:
    """Manager for publishing signals as items in Clarify.

    Items are the published version of signals that are visible
    to the entire organization in Clarify.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        signal_manager: ClarifySignalManager,
        auto_publish: bool = False,
        default_visible: bool = True,
    ) -> None:
        """Initialize the item manager.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient instance for API communication.
            signal_manager: Signal manager to get signal IDs.
            auto_publish: Automatically publish signals as items.
            default_visible: Default visibility for published items.
        """
        self.hass = hass
        self.client = client
        self.signal_manager = signal_manager
        self.auto_publish = auto_publish
        self.default_visible = default_visible

        # Track published items: {signal_id: item_id}
        self._signal_to_item_id: dict[str, str] = {}

        # Track item metadata: {item_id: Item}
        self._item_metadata: dict[str, Item] = {}

        _LOGGER.debug(
            "Initialized ClarifyItemManager (auto_publish=%s, default_visible=%s)",
            auto_publish,
            default_visible,
        )

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

        # Build item from entity
        item = self._build_item_from_entity(
            entity_id,
            state,
            visible if visible is not None else self.default_visible,
            labels,
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
    ) -> Item:
        """Build an Item from Home Assistant entity.

        Args:
            entity_id: Home Assistant entity ID.
            state: Current state of the entity.
            visible: Whether the item should be visible.
            additional_labels: Additional labels to add.

        Returns:
            Item with metadata.
        """
        # Extract domain and name
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

        # Get name and description
        name = entity_id
        description = f"Home Assistant {domain} entity"

        if state is not None and state.attributes:
            # Get friendly name
            name = state.attributes.get("friendly_name", entity_id)

            # Get unit and device class
            unit = state.attributes.get("unit_of_measurement")
            device_class = state.attributes.get("device_class")

            # Build description
            description_parts = [f"Home Assistant {domain} entity"]
            if device_class:
                description_parts.append(f"Device class: {device_class}")
            if unit:
                description_parts.append(f"Unit: {unit}")
            description = " | ".join(description_parts)

        # Build labels
        labels: dict[str, list[str]] = {
            "source": ["Home Assistant"],
            "domain": [domain],
            "entity_id": [entity_id],
            "integration": [self.signal_manager.integration_id],
        }

        # Add additional labels
        if additional_labels:
            for key, values in additional_labels.items():
                if key in labels:
                    # Merge with existing
                    labels[key].extend(values)
                else:
                    labels[key] = values

        # Add state attributes as labels
        if state is not None and state.attributes:
            if "unit_of_measurement" in state.attributes:
                labels["unit"] = [state.attributes["unit_of_measurement"]]
            if "device_class" in state.attributes:
                labels["device_class"] = [state.attributes["device_class"]]

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
    def published_entities(self) -> list[str]:
        """Get list of published entity IDs."""
        published = []
        for entity_id in self.signal_manager.tracked_entities:
            if self.is_published(entity_id):
                published.append(entity_id)
        return published
