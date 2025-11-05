"""Entity listener for tracking Home Assistant state changes."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from .coordinator import ClarifyDataCoordinator
from .signal_manager import ClarifySignalManager
from .const import SUPPORTED_DOMAINS, NUMERIC_ATTRIBUTES

_LOGGER = logging.getLogger(__name__)


class ClarifyEntityListener:
    """Listen to Home Assistant entity state changes and send to Clarify.

    This class tracks state changes for specified entities and formats
    the data for batch sending to Clarify.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ClarifyDataCoordinator,
        signal_manager: ClarifySignalManager,
        include_domains: list[str] | None = None,
        exclude_entities: list[str] | None = None,
    ) -> None:
        """Initialize the entity listener.

        Args:
            hass: Home Assistant instance.
            coordinator: Data coordinator for batch processing.
            signal_manager: Signal manager for metadata.
            include_domains: List of domains to include (default: all supported).
            exclude_entities: List of entity IDs to exclude.
        """
        self.hass = hass
        self.coordinator = coordinator
        self.signal_manager = signal_manager

        self.include_domains = include_domains or SUPPORTED_DOMAINS
        self.exclude_entities = set(exclude_entities or [])

        # Track subscriptions
        self._unsub_listeners: list[callable] = []

        # Statistics
        self.events_processed = 0
        self.events_ignored = 0

        _LOGGER.debug(
            "Initialized ClarifyEntityListener with domains: %s, excluded: %d entities",
            self.include_domains,
            len(self.exclude_entities),
        )

    async def async_start(self) -> None:
        """Start listening to state changes."""
        _LOGGER.info("Starting entity listener for domains: %s", self.include_domains)

        # Get all entities matching our criteria
        entities_to_track = self._get_entities_to_track()

        if not entities_to_track:
            _LOGGER.warning("No entities found to track")
            return

        _LOGGER.info("Tracking %d entities", len(entities_to_track))

        # Create signals for all entities
        await self._async_create_signals_for_entities(entities_to_track)

        # Subscribe to state changes
        unsub = async_track_state_change_event(
            self.hass,
            entities_to_track,
            self._async_state_change_listener,
        )
        self._unsub_listeners.append(unsub)

    async def async_stop(self) -> None:
        """Stop listening to state changes."""
        _LOGGER.info("Stopping entity listener")

        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    def _get_entities_to_track(self) -> list[str]:
        """Get list of entity IDs to track.

        Returns:
            List of entity IDs matching the filter criteria.
        """
        entities = []

        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]

            # Check domain filter
            if domain not in self.include_domains:
                continue

            # Check exclude list
            if entity_id in self.exclude_entities:
                continue

            # Only track entities with numeric states or numeric attributes
            if self._is_trackable_entity(state):
                entities.append(entity_id)

        return entities

    def _is_trackable_entity(self, state: State) -> bool:
        """Check if an entity should be tracked.

        Args:
            state: Entity state.

        Returns:
            True if entity has numeric data to track.
        """
        # Check if state is numeric
        try:
            float(state.state)
            return True
        except (ValueError, TypeError):
            pass

        # Check for numeric attributes
        if state.attributes:
            for attr in NUMERIC_ATTRIBUTES:
                if attr in state.attributes:
                    try:
                        float(state.attributes[attr])
                        return True
                    except (ValueError, TypeError):
                        continue

        return False

    async def _async_create_signals_for_entities(
        self,
        entity_ids: list[str],
    ) -> None:
        """Create Clarify signals for all tracked entities.

        Args:
            entity_ids: List of entity IDs to create signals for.
        """
        _LOGGER.info("Creating signals for %d entities", len(entity_ids))

        for entity_id in entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                await self.signal_manager.async_ensure_signal(entity_id, state)
            except Exception as err:
                _LOGGER.error("Failed to create signal for %s: %s", entity_id, err)

        _LOGGER.info("Signal creation complete: %d signals", self.signal_manager.signal_count)

    @callback
    def _async_state_change_listener(self, event: Event) -> None:
        """Handle state change events.

        Args:
            event: State change event.
        """
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")
        old_state: State | None = event.data.get("old_state")

        if not entity_id or not new_state:
            return

        # Ignore unavailable/unknown states
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self.events_ignored += 1
            return

        # Process the state change
        self.hass.async_create_task(
            self._async_process_state_change(entity_id, new_state, old_state)
        )

    async def _async_process_state_change(
        self,
        entity_id: str,
        new_state: State,
        old_state: State | None,
    ) -> None:
        """Process a state change and add data to coordinator.

        Args:
            entity_id: Entity ID that changed.
            new_state: New state.
            old_state: Previous state.
        """
        try:
            # Ensure signal exists
            input_id = await self.signal_manager.async_ensure_signal(entity_id, new_state)

            # Extract numeric values from state
            values = self._extract_numeric_values(entity_id, new_state)

            if not values:
                self.events_ignored += 1
                return

            # Add data points to coordinator
            timestamp = new_state.last_updated

            for suffix, value in values.items():
                # Create unique input_id for each value
                # Main state uses base input_id, attributes get suffix
                data_input_id = f"{input_id}_{suffix}" if suffix else input_id

                # Ensure signal exists for attribute if needed
                if suffix:
                    await self._async_ensure_attribute_signal(
                        entity_id, suffix, new_state, data_input_id
                    )

                # Add data point
                await self.coordinator.add_data_point(
                    input_id=data_input_id,
                    value=value,
                    timestamp=timestamp,
                )

            self.events_processed += 1

            _LOGGER.debug(
                "Processed state change for %s: %d values added",
                entity_id,
                len(values),
            )

        except Exception as err:
            _LOGGER.error("Error processing state change for %s: %s", entity_id, err)
            self.events_ignored += 1

    def _extract_numeric_values(
        self,
        entity_id: str,
        state: State,
    ) -> dict[str, float]:
        """Extract numeric values from entity state.

        Args:
            entity_id: Entity ID.
            state: Entity state.

        Returns:
            Dictionary of {suffix: value} pairs. Empty suffix for main state value.
        """
        values: dict[str, float] = {}

        # Try to extract main state value
        try:
            value = float(state.state)
            values[""] = value  # Empty suffix for main state
        except (ValueError, TypeError):
            pass

        # Extract numeric attributes
        if state.attributes:
            for attr in NUMERIC_ATTRIBUTES:
                if attr in state.attributes:
                    try:
                        value = float(state.attributes[attr])
                        values[attr] = value
                    except (ValueError, TypeError):
                        continue

        return values

    async def _async_ensure_attribute_signal(
        self,
        entity_id: str,
        attribute: str,
        state: State,
        input_id: str,
    ) -> None:
        """Ensure a signal exists for an entity attribute.

        Args:
            entity_id: Entity ID.
            attribute: Attribute name.
            state: Entity state.
            input_id: Input ID for the attribute signal.
        """
        # Check if signal already exists
        if input_id in self.signal_manager._signal_metadata:
            return

        # Create signal for attribute
        from pyclarify.views.signals import SignalInfo

        name = f"{state.attributes.get('friendly_name', entity_id)} - {attribute}"
        description = f"Attribute '{attribute}' from {entity_id}"

        # Get unit if available
        unit = None
        if attribute == "temperature":
            unit = "°C"  # Default, could be from ATTR_UNIT_OF_MEASUREMENT
        elif attribute in state.attributes:
            # Try to infer unit
            pass

        labels = {
            "source": ["Home Assistant"],
            "integration": [self.signal_manager.integration_id],
            "domain": [entity_id.split(".")[0]],
            "entity_id": [entity_id],
            "attribute": [attribute],
        }

        if unit:
            labels["unit"] = [unit]

        signal = SignalInfo(
            name=name,
            description=description,
            labels=labels,
        )

        try:
            await self.signal_manager.client.async_save_signals(
                input_ids=[input_id],
                signals=[signal],
                create_only=False,
            )

            # Store in signal manager
            self.signal_manager._signal_metadata[input_id] = signal

        except Exception as err:
            _LOGGER.error("Failed to create attribute signal for %s.%s: %s", entity_id, attribute, err)

    @property
    def tracked_entity_count(self) -> int:
        """Get number of tracked entities."""
        return len(self.signal_manager.tracked_entities)
