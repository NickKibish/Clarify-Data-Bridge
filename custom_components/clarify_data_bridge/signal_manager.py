"""Signal manager for creating and managing Clarify signals."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, State
from pyclarify.views.signals import SignalInfo

from .clarify_client import ClarifyClient, ClarifyConnectionError
from .entity_selector import EntityMetadata, EntitySelector

_LOGGER = logging.getLogger(__name__)


class ClarifySignalManager:
    """Manager for creating and tracking Clarify signals.

    This class manages the mapping between Home Assistant entities and Clarify signals,
    ensuring signals are created with proper metadata.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        integration_id: str,
        entity_selector: EntitySelector | None = None,
    ) -> None:
        """Initialize the signal manager.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient instance for API communication.
            integration_id: Clarify integration ID for labeling.
            entity_selector: Optional EntitySelector for enhanced metadata.
        """
        self.hass = hass
        self.client = client
        self.integration_id = integration_id
        self.entity_selector = entity_selector

        # Track created signals: {entity_id: input_id}
        self._entity_to_input_id: dict[str, str] = {}

        # Track signal metadata: {input_id: SignalInfo}
        self._signal_metadata: dict[str, SignalInfo] = {}

        # Cache entity metadata: {entity_id: EntityMetadata}
        self._entity_metadata_cache: dict[str, EntityMetadata] = {}

        _LOGGER.debug("Initialized ClarifySignalManager")

    def get_input_id(self, entity_id: str) -> str:
        """Get or create input ID for an entity.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            Clarify input ID for the entity.
        """
        if entity_id not in self._entity_to_input_id:
            # Create a unique input ID based on entity_id
            # Format: ha_<integration_id>_<entity_id_with_underscores>
            input_id = f"ha_{self.integration_id}_{entity_id.replace('.', '_')}"
            self._entity_to_input_id[entity_id] = input_id
            _LOGGER.debug("Created input_id for %s: %s", entity_id, input_id)

        return self._entity_to_input_id[entity_id]

    async def async_ensure_signal(
        self,
        entity_id: str,
        state: State | None = None,
    ) -> str:
        """Ensure a signal exists for the given entity.

        Args:
            entity_id: Home Assistant entity ID.
            state: Current state of the entity (optional).

        Returns:
            Input ID for the signal.
        """
        input_id = self.get_input_id(entity_id)

        # If signal already exists, return input_id
        if input_id in self._signal_metadata:
            return input_id

        # Get state if not provided
        if state is None:
            state = self.hass.states.get(entity_id)

        # Create signal with metadata
        await self._async_create_signal(entity_id, input_id, state)

        return input_id

    async def _async_create_signal(
        self,
        entity_id: str,
        input_id: str,
        state: State | None,
    ) -> None:
        """Create a Clarify signal with metadata from entity.

        Args:
            entity_id: Home Assistant entity ID.
            input_id: Clarify input ID.
            state: Current state of the entity.
        """
        # Build signal metadata from entity (with enhanced metadata if available)
        signal_info = await self._async_build_signal_info(entity_id, state)

        try:
            # Save signal to Clarify
            _LOGGER.info("Creating Clarify signal for entity: %s (input_id: %s)", entity_id, input_id)
            await self.client.async_save_signals(
                input_ids=[input_id],
                signals=[signal_info],
                create_only=False,
            )

            # Store metadata
            self._signal_metadata[input_id] = signal_info

            _LOGGER.debug("Successfully created signal for %s", entity_id)

        except ClarifyConnectionError as err:
            _LOGGER.error("Failed to create signal for %s: %s", entity_id, err)
            raise

    async def _async_build_signal_info(
        self,
        entity_id: str,
        state: State | None,
    ) -> SignalInfo:
        """Build SignalInfo from Home Assistant entity with enhanced metadata.

        Args:
            entity_id: Home Assistant entity ID.
            state: Current state of the entity.

        Returns:
            SignalInfo with metadata.
        """
        # Try to get enhanced metadata from EntitySelector
        entity_metadata = None
        if self.entity_selector:
            # Check cache first
            if entity_id in self._entity_metadata_cache:
                entity_metadata = self._entity_metadata_cache[entity_id]
            else:
                # Get fresh metadata
                entity_metadata = await self.entity_selector.async_get_entity_metadata(entity_id, state)
                if entity_metadata:
                    self._entity_metadata_cache[entity_id] = entity_metadata

        # Use enhanced metadata if available
        if entity_metadata:
            labels = entity_metadata.to_labels()
            # Add integration ID to labels
            labels["integration"] = [self.integration_id]

            signal = SignalInfo(
                name=entity_metadata.friendly_name,
                description=entity_metadata.description or f"Home Assistant {entity_metadata.domain} entity",
                labels=labels,
            )
        else:
            # Fall back to basic metadata extraction
            signal = self._build_signal_info_basic(entity_id, state)

        return signal

    def _build_signal_info_basic(
        self,
        entity_id: str,
        state: State | None,
    ) -> SignalInfo:
        """Build SignalInfo from Home Assistant entity (basic method).

        Args:
            entity_id: Home Assistant entity ID.
            state: Current state of the entity.

        Returns:
            SignalInfo with basic metadata.
        """
        # Extract domain and name
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        object_id = entity_id.split(".")[1] if "." in entity_id else entity_id

        # Get friendly name
        name = entity_id
        description = f"Home Assistant {domain} entity"
        unit = None
        device_class = None

        if state is not None and state.attributes:
            # Get friendly name
            name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)

            # Get unit of measurement
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

            # Get device class
            device_class = state.attributes.get(ATTR_DEVICE_CLASS)

            # Build description
            description_parts = [f"Home Assistant {domain} entity"]
            if device_class:
                description_parts.append(f"Device class: {device_class}")
            if unit:
                description_parts.append(f"Unit: {unit}")
            description = " | ".join(description_parts)

        # Build labels for categorization
        labels: dict[str, list[str]] = {
            "source": ["Home Assistant"],
            "integration": [self.integration_id],
            "domain": [domain],
            "entity_id": [entity_id],
        }

        if device_class:
            labels["device_class"] = [device_class]

        if unit:
            labels["unit"] = [unit]

        # Create SignalInfo
        signal = SignalInfo(
            name=name,
            description=description,
            labels=labels,
        )

        return signal

    async def async_update_signal_metadata(
        self,
        entity_id: str,
        state: State,
    ) -> None:
        """Update signal metadata if entity attributes changed.

        Args:
            entity_id: Home Assistant entity ID.
            state: New state of the entity.
        """
        input_id = self.get_input_id(entity_id)

        # Check if signal exists
        if input_id not in self._signal_metadata:
            # Signal doesn't exist yet, create it
            await self.async_ensure_signal(entity_id, state)
            return

        # Invalidate cache for this entity
        if entity_id in self._entity_metadata_cache:
            del self._entity_metadata_cache[entity_id]

        # Build new metadata
        new_signal_info = await self._async_build_signal_info(entity_id, state)

        # Check if metadata changed (compare relevant fields)
        old_signal_info = self._signal_metadata[input_id]

        if (
            new_signal_info.name != old_signal_info.name
            or new_signal_info.description != old_signal_info.description
        ):
            _LOGGER.info("Updating metadata for signal %s", entity_id)

            try:
                await self.client.async_save_signals(
                    input_ids=[input_id],
                    signals=[new_signal_info],
                    create_only=False,
                )

                # Update stored metadata
                self._signal_metadata[input_id] = new_signal_info

            except ClarifyConnectionError as err:
                _LOGGER.error("Failed to update signal metadata for %s: %s", entity_id, err)

    def get_entity_metadata(self, entity_id: str) -> EntityMetadata | None:
        """Get cached entity metadata.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            EntityMetadata if cached, None otherwise.
        """
        return self._entity_metadata_cache.get(entity_id)

    def is_signal_created(self, entity_id: str) -> bool:
        """Check if a signal has been created for an entity.

        Args:
            entity_id: Home Assistant entity ID.

        Returns:
            True if signal exists.
        """
        input_id = self.get_input_id(entity_id)
        return input_id in self._signal_metadata

    @property
    def tracked_entities(self) -> list[str]:
        """Get list of tracked entity IDs."""
        return list(self._entity_to_input_id.keys())

    @property
    def signal_count(self) -> int:
        """Get number of created signals."""
        return len(self._signal_metadata)
