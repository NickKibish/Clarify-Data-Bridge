"""Entity listener for tracking Home Assistant state changes."""
from __future__ import annotations

from datetime import timedelta
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
from .entity_selector import EntitySelector, EntityMetadata
from .const import SUPPORTED_DOMAINS, NUMERIC_ATTRIBUTES
from .data_validator import DataValidator, ValidationResult

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
        entity_selector: EntitySelector | None = None,
        include_domains: list[str] | None = None,
        exclude_entities: list[str] | None = None,
        include_device_classes: list[str] | None = None,
        exclude_device_classes: list[str] | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        selected_entities: list[str] | None = None,
    ) -> None:
        """Initialize the entity listener.

        Args:
            hass: Home Assistant instance.
            coordinator: Data coordinator for batch processing.
            signal_manager: Signal manager for metadata.
            entity_selector: Optional EntitySelector for advanced entity discovery.
            include_domains: List of domains to include (default: all supported).
            exclude_entities: List of entity IDs to exclude.
            include_device_classes: List of device classes to include.
            exclude_device_classes: List of device classes to exclude.
            include_patterns: Regex patterns for entity IDs to include.
            exclude_patterns: Regex patterns for entity IDs to exclude.
            selected_entities: Specific entity IDs to track (if None, discover automatically).
        """
        self.hass = hass
        self.coordinator = coordinator
        self.signal_manager = signal_manager
        self.entity_selector = entity_selector

        # Filtering options
        self.include_domains = include_domains or SUPPORTED_DOMAINS
        self.exclude_entities = set(exclude_entities or [])
        self.include_device_classes = include_device_classes
        self.exclude_device_classes = exclude_device_classes
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.selected_entities = set(selected_entities or [])

        # Track discovered entities
        self._discovered_entities: dict[str, EntityMetadata] = {}

        # Track subscriptions
        self._unsub_listeners: list[callable] = []

        # Initialize data validator
        self.data_validator = DataValidator(
            stale_threshold=timedelta(minutes=5),  # Data older than 5 minutes is stale
            validate_ranges=True,
            track_changes_only=False,  # Track all changes, not just value changes
        )

        # Statistics
        self.events_processed = 0
        self.events_ignored = 0
        self.validation_failed = 0

        _LOGGER.debug(
            "Initialized ClarifyEntityListener with domains: %s, excluded: %d entities, selected: %d entities",
            self.include_domains,
            len(self.exclude_entities),
            len(self.selected_entities),
        )

    async def async_start(self) -> None:
        """Start listening to state changes with intelligent entity discovery."""
        _LOGGER.info("Starting entity listener for domains: %s", self.include_domains)
        _LOGGER.debug(
            "Entity listener config: selected_entities=%d, include_device_classes=%s, exclude_device_classes=%s",
            len(self.selected_entities),
            self.include_device_classes,
            self.exclude_device_classes,
        )

        # Use EntitySelector if available for advanced discovery
        if self.entity_selector:
            await self._async_discover_entities_advanced()
        else:
            await self._async_discover_entities_basic()

        if not self._discovered_entities:
            _LOGGER.warning("No entities found to track")
            return

        entity_ids = list(self._discovered_entities.keys())
        _LOGGER.info("Tracking %d entities", len(entity_ids))

        # Log first 10 entities for debugging
        if entity_ids:
            sample_entities = entity_ids[:10]
            _LOGGER.debug("Sample of tracked entities (first 10): %s", sample_entities)
            _LOGGER.debug("Total discovered entities: %s", len(entity_ids))

        # Log entity breakdown by category if using EntitySelector
        if self.entity_selector:
            self._log_entity_discovery_summary()

        # Create signals for all entities
        await self._async_create_signals_for_entities(entity_ids)

        # Subscribe to state changes
        _LOGGER.debug("Subscribing to state changes for %d entities", len(entity_ids))
        unsub = async_track_state_change_event(
            self.hass,
            entity_ids,
            self._async_state_change_listener,
        )
        self._unsub_listeners.append(unsub)
        _LOGGER.info("Entity listener started successfully - now monitoring %d entities", len(entity_ids))

    async def _async_discover_entities_advanced(self) -> None:
        """Discover entities using EntitySelector with advanced filtering."""
        _LOGGER.info("Using advanced entity discovery with EntitySelector")

        # If selected_entities is specified, use it directly
        if self.selected_entities:
            _LOGGER.info("Using user-selected entities: %d specified", len(self.selected_entities))
            for entity_id in self.selected_entities:
                state = self.hass.states.get(entity_id)
                if state:
                    metadata = await self.entity_selector.async_get_entity_metadata(entity_id, state)
                    if metadata:
                        self._discovered_entities[entity_id] = metadata
                else:
                    _LOGGER.warning("Selected entity %s not found", entity_id)
        else:
            # Use automatic discovery
            discovered = await self.entity_selector.async_discover_entities(
                include_domains=self.include_domains,
                exclude_domains=None,
                include_device_classes=self.include_device_classes,
                exclude_device_classes=self.exclude_device_classes,
                include_entity_ids=None,
                exclude_entity_ids=list(self.exclude_entities),
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
            )

            # Store discovered entities
            for metadata in discovered:
                self._discovered_entities[metadata.entity_id] = metadata

        _LOGGER.info(
            "Advanced discovery found %d entities",
            len(self._discovered_entities),
        )

    async def _async_discover_entities_basic(self) -> None:
        """Discover entities using basic filtering (legacy method)."""
        _LOGGER.info("Using basic entity discovery")

        entities = self._get_entities_to_track()

        # Create basic metadata for discovered entities
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            metadata = EntityMetadata(
                entity_id=entity_id,
                domain=entity_id.split(".")[0],
                object_id=entity_id.split(".", 1)[1],
                friendly_name=state.attributes.get("friendly_name", entity_id) if state else entity_id,
                has_numeric_state=self._is_numeric(state.state) if state else False,
            )
            self._discovered_entities[entity_id] = metadata

        _LOGGER.info("Basic discovery found %d entities", len(self._discovered_entities))

    def _log_entity_discovery_summary(self) -> None:
        """Log a summary of discovered entities."""
        from collections import Counter

        # Count by category
        category_counts = Counter(m.category.value for m in self._discovered_entities.values())

        # Count by domain
        domain_counts = Counter(m.domain for m in self._discovered_entities.values())

        _LOGGER.info("Entity discovery summary:")
        _LOGGER.info("  By domain: %s", dict(domain_counts))
        _LOGGER.info("  By category: %s", dict(category_counts))

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
        if self._is_numeric(state.state):
            return True

        # Check for numeric attributes
        if state.attributes:
            for attr in NUMERIC_ATTRIBUTES:
                if attr in state.attributes:
                    if self._is_numeric(state.attributes[attr]):
                        return True

        return False

    def _is_numeric(self, value: Any) -> bool:
        """Check if a value is numeric.

        Args:
            value: Value to check.

        Returns:
            True if value is numeric.
        """
        if value in (STATE_UNAVAILABLE, STATE_UNKNOWN, None):
            return False

        try:
            float(value)
            return True
        except (ValueError, TypeError):
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

        # DEBUG: Log every state change callback
        _LOGGER.debug("State change callback triggered for: %s (new_state=%s)", entity_id, new_state.state if new_state else "None")

        if not entity_id or not new_state:
            _LOGGER.debug("Ignoring state change - missing entity_id or new_state")
            return

        # Ignore unavailable/unknown states
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug("Ignoring state change for %s - state is %s", entity_id, new_state.state)
            self.events_ignored += 1
            return

        # DEBUG: Log that we're processing
        _LOGGER.debug("Processing state change: %s = %s (was %s)", entity_id, new_state.state, old_state.state if old_state else "None")

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
            # Get entity metadata for device class
            metadata = self._discovered_entities.get(entity_id)
            device_class = metadata.device_class if metadata else None

            _LOGGER.debug("Processing %s: device_class=%s", entity_id, device_class)

            # Ensure signal exists
            input_id = await self.signal_manager.async_ensure_signal(entity_id, new_state)
            _LOGGER.debug("Signal ensured for %s: input_id=%s", entity_id, input_id)

            # Extract and validate numeric values from state
            values = self._extract_and_validate_numeric_values(entity_id, new_state, device_class)
            _LOGGER.debug("Extracted values for %s: %s", entity_id, values)

            if not values:
                _LOGGER.debug("No valid numeric values extracted for %s - ignoring", entity_id)
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
                _LOGGER.debug("Adding data point: %s = %s (timestamp=%s)", data_input_id, value, timestamp)
                await self.coordinator.add_data_point(
                    input_id=data_input_id,
                    value=value,
                    timestamp=timestamp,
                    entity_id=entity_id,
                    device_class=device_class,
                )

            self.events_processed += 1

            _LOGGER.info(
                "✓ Processed state change for %s: %d values added",
                entity_id,
                len(values),
            )

        except Exception as err:
            _LOGGER.error("Error processing state change for %s: %s", entity_id, err, exc_info=True)
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
        # Use EntitySelector if available for better extraction
        if self.entity_selector and entity_id in self._discovered_entities:
            metadata = self._discovered_entities[entity_id]
            return self.entity_selector.extract_numeric_values(state, metadata)

        # Fall back to basic extraction
        values: dict[str, float] = {}

        # Try to extract main state value
        if self._is_numeric(state.state):
            # Binary sensor special case
            if state.domain == "binary_sensor":
                values[""] = 1.0 if state.state == "on" else 0.0
            else:
                values[""] = float(state.state)

        # Extract numeric attributes
        if state.attributes:
            for attr in NUMERIC_ATTRIBUTES:
                if attr in state.attributes and self._is_numeric(state.attributes[attr]):
                    try:
                        values[attr] = float(state.attributes[attr])
                    except (ValueError, TypeError):
                        continue

        return values

    def _extract_and_validate_numeric_values(
        self,
        entity_id: str,
        state: State,
        device_class: str | None = None,
    ) -> dict[str, float]:
        """Extract and validate numeric values from entity state.

        Uses DataValidator to ensure data quality.

        Args:
            entity_id: Entity ID.
            state: Entity state.
            device_class: Device class for validation.

        Returns:
            Dictionary of {suffix: value} pairs for valid values only.
        """
        validated_values: dict[str, float] = {}

        _LOGGER.debug("Validating %s: state=%s, device_class=%s", entity_id, state.state, device_class)

        # Validate main state value
        result = self.data_validator.validate_state(
            state=state,
            entity_id=entity_id,
            device_class=device_class,
        )

        _LOGGER.debug("Validation result for %s: %s (value=%s → %s)",
                     entity_id, result.result, result.original_value, result.value)

        if result.result == ValidationResult.VALID:
            validated_values[""] = result.value
            _LOGGER.debug("✓ Main state validated: %s = %s", entity_id, result.value)
        elif result.result != ValidationResult.INVALID_STATE:
            # Log validation failures (except invalid states which are expected)
            _LOGGER.warning(
                "✗ Validation failed for %s: %s (value=%s, result=%s)",
                entity_id,
                result.reason,
                result.original_value,
                result.result,
            )
            self.validation_failed += 1
        else:
            _LOGGER.debug("State is not numeric for %s: %s", entity_id, state.state)

        # Validate numeric attributes
        if state.attributes:
            for attr in NUMERIC_ATTRIBUTES:
                if attr not in state.attributes:
                    continue

                attr_result = self.data_validator.validate_attribute(
                    state=state,
                    attribute=attr,
                    entity_id=f"{entity_id}.{attr}",
                    device_class=device_class,
                )

                if attr_result.result == ValidationResult.VALID:
                    validated_values[attr] = attr_result.value
                elif attr_result.result != ValidationResult.INVALID_STATE:
                    _LOGGER.debug(
                        "Validation failed for %s.%s: %s",
                        entity_id,
                        attr,
                        attr_result.reason,
                    )

        return validated_values

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
        return len(self._discovered_entities)

    @property
    def discovered_entities(self) -> dict[str, EntityMetadata]:
        """Get discovered entities with metadata."""
        return self._discovered_entities
