"""Data validation and conversion for Home Assistant states."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import math
from typing import Any

from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OPEN,
    STATE_CLOSED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.components.lock import LockState
from homeassistant.core import State
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of data validation."""

    VALID = "valid"
    INVALID_STATE = "invalid_state"  # Unavailable/unknown
    INVALID_TYPE = "invalid_type"  # Not numeric, not convertible
    INVALID_RANGE = "invalid_range"  # Out of reasonable bounds
    STALE = "stale"  # Data is too old
    UNCHANGED = "unchanged"  # Value hasn't changed (for change-only tracking)
    DUPLICATE = "duplicate"  # Same timestamp already processed


@dataclass
class ValidatedData:
    """Result of data validation and conversion."""

    result: ValidationResult
    value: float | None = None
    original_value: Any = None
    converted: bool = False
    unit: str | None = None
    timestamp: datetime | None = None
    reason: str | None = None


class DataValidator:
    """Validates and converts Home Assistant state data for Clarify.io.

    Handles:
    - Boolean to numeric conversion (on/off -> 1/0)
    - State validation (filter unavailable/unknown)
    - Numeric range validation
    - Stale data detection
    - Type conversion
    - Unit extraction
    """

    # Boolean state mappings to numeric values
    BOOLEAN_STATE_MAP = {
        STATE_ON: 1.0,
        STATE_OFF: 0.0,
        STATE_HOME: 1.0,
        STATE_NOT_HOME: 0.0,
        STATE_OPEN: 1.0,
        STATE_CLOSED: 0.0,
        LockState.LOCKED: 1.0,
        LockState.UNLOCKED: 0.0,
        "true": 1.0,
        "false": 0.0,
        "yes": 1.0,
        "no": 0.0,
        "active": 1.0,
        "inactive": 0.0,
        "detected": 1.0,
        "clear": 0.0,
    }

    # Invalid states to reject
    INVALID_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN, None, "", "None", "none"}

    # Reasonable numeric ranges for validation
    # Format: {device_class: (min, max)}
    NUMERIC_RANGES = {
        "temperature": (-100, 200),  # Celsius, extreme range
        "humidity": (0, 100),  # Percentage
        "pressure": (0, 2000),  # hPa/mbar
        "battery": (0, 100),  # Percentage
        "brightness": (0, 255),  # Standard LED range
        "volume_level": (0, 1),  # Home Assistant standard
        "pm25": (0, 1000),  # µg/m³
        "pm10": (0, 1000),  # µg/m³
        "carbon_dioxide": (0, 10000),  # ppm
        "aqi": (0, 500),  # Air Quality Index
        "illuminance": (0, 200000),  # lux
        "power": (-50000, 50000),  # Watts (negative for solar)
        "energy": (0, 1000000),  # kWh
        "voltage": (0, 500),  # Volts
        "current": (0, 100),  # Amps
        "power_factor": (-1, 1),  # Ratio
    }

    def __init__(
        self,
        stale_threshold: timedelta | None = None,
        validate_ranges: bool = True,
        track_changes_only: bool = False,
    ) -> None:
        """Initialize the data validator.

        Args:
            stale_threshold: Maximum age for data to be considered fresh.
                If None, no staleness check is performed.
            validate_ranges: Whether to validate numeric ranges.
            track_changes_only: If True, only report values that have changed.
        """
        self.stale_threshold = stale_threshold
        self.validate_ranges = validate_ranges
        self.track_changes_only = track_changes_only

        # Track last values for change detection
        self._last_values: dict[str, tuple[float, datetime]] = {}

        # Statistics
        self.validation_stats = {
            "total": 0,
            "valid": 0,
            "converted": 0,
            "invalid_state": 0,
            "invalid_type": 0,
            "invalid_range": 0,
            "stale": 0,
            "unchanged": 0,
        }

    def validate_and_convert(
        self,
        value: Any,
        entity_id: str | None = None,
        state: State | None = None,
        device_class: str | None = None,
        timestamp: datetime | None = None,
    ) -> ValidatedData:
        """Validate and convert a value to numeric format.

        Args:
            value: Value to validate and convert.
            entity_id: Entity ID for tracking (optional).
            state: Full state object for additional context (optional).
            device_class: Device class for range validation (optional).
            timestamp: Timestamp of the value (optional).

        Returns:
            ValidatedData with result and converted value.
        """
        self.validation_stats["total"] += 1

        # Use current time if no timestamp provided
        if timestamp is None:
            timestamp = dt_util.utcnow()

        # Check for invalid states first
        if value in self.INVALID_STATES:
            self.validation_stats["invalid_state"] += 1
            return ValidatedData(
                result=ValidationResult.INVALID_STATE,
                original_value=value,
                timestamp=timestamp,
                reason=f"Invalid state: {value}",
            )

        # Check staleness
        if self.stale_threshold is not None:
            if timestamp < dt_util.utcnow() - self.stale_threshold:
                self.validation_stats["stale"] += 1
                return ValidatedData(
                    result=ValidationResult.STALE,
                    original_value=value,
                    timestamp=timestamp,
                    reason=f"Data is stale (older than {self.stale_threshold})",
                )

        # Try to convert to numeric
        numeric_value, converted = self._convert_to_numeric(value)

        if numeric_value is None:
            self.validation_stats["invalid_type"] += 1
            return ValidatedData(
                result=ValidationResult.INVALID_TYPE,
                original_value=value,
                timestamp=timestamp,
                reason=f"Cannot convert to numeric: {type(value).__name__}",
            )

        # Validate numeric value
        if not self._is_valid_numeric(numeric_value):
            self.validation_stats["invalid_type"] += 1
            return ValidatedData(
                result=ValidationResult.INVALID_TYPE,
                value=numeric_value,
                original_value=value,
                timestamp=timestamp,
                reason="Numeric value is NaN or infinite",
            )

        # Range validation
        if self.validate_ranges and device_class:
            if not self._is_in_valid_range(numeric_value, device_class):
                self.validation_stats["invalid_range"] += 1
                range_info = self.NUMERIC_RANGES.get(device_class, "unknown")
                return ValidatedData(
                    result=ValidationResult.INVALID_RANGE,
                    value=numeric_value,
                    original_value=value,
                    converted=converted,
                    timestamp=timestamp,
                    reason=f"Value {numeric_value} outside valid range {range_info} for {device_class}",
                )

        # Change detection
        if self.track_changes_only and entity_id:
            if not self._has_value_changed(entity_id, numeric_value, timestamp):
                self.validation_stats["unchanged"] += 1
                return ValidatedData(
                    result=ValidationResult.UNCHANGED,
                    value=numeric_value,
                    original_value=value,
                    converted=converted,
                    timestamp=timestamp,
                    reason="Value unchanged since last update",
                )

        # Extract unit if available
        unit = None
        if state and state.attributes:
            unit = state.attributes.get("unit_of_measurement")

        # Valid data
        self.validation_stats["valid"] += 1
        if converted:
            self.validation_stats["converted"] += 1

        return ValidatedData(
            result=ValidationResult.VALID,
            value=numeric_value,
            original_value=value,
            converted=converted,
            unit=unit,
            timestamp=timestamp,
        )

    def _convert_to_numeric(self, value: Any) -> tuple[float | None, bool]:
        """Convert a value to numeric format.

        Args:
            value: Value to convert.

        Returns:
            Tuple of (numeric_value, was_converted).
            If conversion fails, returns (None, False).
        """
        # Already numeric
        if isinstance(value, (int, float)):
            return float(value), False

        # Try direct string to float conversion
        if isinstance(value, str):
            # Check boolean state mapping first
            value_lower = value.lower()
            if value_lower in self.BOOLEAN_STATE_MAP:
                return self.BOOLEAN_STATE_MAP[value_lower], True

            # Try numeric conversion
            try:
                return float(value), False
            except (ValueError, TypeError):
                pass

        # Boolean conversion
        if isinstance(value, bool):
            return 1.0 if value else 0.0, True

        # Cannot convert
        return None, False

    def _is_valid_numeric(self, value: float) -> bool:
        """Check if a numeric value is valid (not NaN or infinite).

        Args:
            value: Numeric value to check.

        Returns:
            True if valid.
        """
        return not (math.isnan(value) or math.isinf(value))

    def _is_in_valid_range(self, value: float, device_class: str) -> bool:
        """Check if a value is within valid range for its device class.

        Args:
            value: Numeric value.
            device_class: Device class.

        Returns:
            True if in valid range or no range defined.
        """
        if device_class not in self.NUMERIC_RANGES:
            return True  # No range defined, accept any value

        min_val, max_val = self.NUMERIC_RANGES[device_class]
        return min_val <= value <= max_val

    def _has_value_changed(
        self,
        entity_id: str,
        value: float,
        timestamp: datetime,
    ) -> bool:
        """Check if value has changed since last update.

        Args:
            entity_id: Entity identifier.
            value: New value.
            timestamp: New timestamp.

        Returns:
            True if value has changed or is first update.
        """
        if entity_id not in self._last_values:
            # First update
            self._last_values[entity_id] = (value, timestamp)
            return True

        last_value, last_timestamp = self._last_values[entity_id]

        # Consider changed if value differs or timestamp is newer
        if value != last_value or timestamp > last_timestamp:
            self._last_values[entity_id] = (value, timestamp)
            return True

        return False

    def validate_state(
        self,
        state: State,
        entity_id: str | None = None,
        device_class: str | None = None,
    ) -> ValidatedData:
        """Validate and convert a Home Assistant state object.

        Args:
            state: Home Assistant state.
            entity_id: Entity ID (defaults to state.entity_id).
            device_class: Device class for validation.

        Returns:
            ValidatedData with result and converted value.
        """
        entity_id = entity_id or state.entity_id

        # Get device class from attributes if not provided
        if device_class is None and state.attributes:
            device_class = state.attributes.get("device_class")

        return self.validate_and_convert(
            value=state.state,
            entity_id=entity_id,
            state=state,
            device_class=device_class,
            timestamp=state.last_updated,
        )

    def validate_attribute(
        self,
        state: State,
        attribute: str,
        entity_id: str | None = None,
        device_class: str | None = None,
    ) -> ValidatedData:
        """Validate and convert a state attribute.

        Args:
            state: Home Assistant state.
            attribute: Attribute name.
            entity_id: Entity ID for tracking.
            device_class: Device class for validation.

        Returns:
            ValidatedData with result and converted value.
        """
        if attribute not in state.attributes:
            return ValidatedData(
                result=ValidationResult.INVALID_STATE,
                reason=f"Attribute '{attribute}' not found",
            )

        value = state.attributes[attribute]
        entity_id = entity_id or f"{state.entity_id}.{attribute}"

        # Try to infer device class from attribute name
        if device_class is None:
            device_class = self._infer_device_class_from_attribute(attribute)

        return self.validate_and_convert(
            value=value,
            entity_id=entity_id,
            state=state,
            device_class=device_class,
            timestamp=state.last_updated,
        )

    def _infer_device_class_from_attribute(self, attribute: str) -> str | None:
        """Infer device class from attribute name.

        Args:
            attribute: Attribute name.

        Returns:
            Inferred device class or None.
        """
        attribute_lower = attribute.lower()

        # Temperature
        if "temp" in attribute_lower:
            return "temperature"

        # Humidity
        if "humid" in attribute_lower:
            return "humidity"

        # Power and energy
        if "power" in attribute_lower:
            return "power"
        if "energy" in attribute_lower:
            return "energy"
        if "voltage" in attribute_lower:
            return "voltage"
        if "current" in attribute_lower:
            return "current"

        # Battery
        if "battery" in attribute_lower:
            return "battery"

        # Brightness
        if "brightness" in attribute_lower:
            return "brightness"

        # Volume
        if "volume" in attribute_lower:
            return "volume_level"

        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get validation statistics.

        Returns:
            Dictionary of statistics.
        """
        total = self.validation_stats["total"]
        if total == 0:
            return {**self.validation_stats, "success_rate": 0.0}

        return {
            **self.validation_stats,
            "success_rate": self.validation_stats["valid"] / total * 100,
        }

    def reset_statistics(self) -> None:
        """Reset validation statistics."""
        for key in self.validation_stats:
            self.validation_stats[key] = 0


class UnitConverter:
    """Converts units for Home Assistant data.

    Handles common unit conversions for time-series data.
    """

    # Conversion factors to SI/standard units
    CONVERSIONS = {
        # Temperature
        "temperature": {
            "°F": lambda f: (f - 32) * 5/9,  # Fahrenheit to Celsius
            "°C": lambda c: c,  # Already Celsius
            "K": lambda k: k - 273.15,  # Kelvin to Celsius
        },
        # Power
        "power": {
            "W": lambda w: w,
            "kW": lambda kw: kw * 1000,
            "MW": lambda mw: mw * 1000000,
        },
        # Energy
        "energy": {
            "Wh": lambda wh: wh / 1000,  # Convert to kWh
            "kWh": lambda kwh: kwh,
            "MWh": lambda mwh: mwh * 1000,
        },
        # Pressure
        "pressure": {
            "hPa": lambda hpa: hpa,
            "mbar": lambda mbar: mbar,
            "Pa": lambda pa: pa / 100,
            "psi": lambda psi: psi * 68.9476,
            "inHg": lambda inhg: inhg * 33.8639,
        },
    }

    @classmethod
    def convert(
        cls,
        value: float,
        from_unit: str,
        device_class: str | None = None,
    ) -> tuple[float, str | None]:
        """Convert a value to standard unit for device class.

        Args:
            value: Value to convert.
            from_unit: Current unit.
            device_class: Device class to determine conversion.

        Returns:
            Tuple of (converted_value, target_unit).
        """
        if device_class not in cls.CONVERSIONS:
            return value, from_unit

        conversions = cls.CONVERSIONS[device_class]

        if from_unit not in conversions:
            return value, from_unit

        converter = conversions[from_unit]
        converted_value = converter(value)

        # Return with standard unit
        standard_units = {
            "temperature": "°C",
            "power": "W",
            "energy": "kWh",
            "pressure": "hPa",
        }

        return converted_value, standard_units.get(device_class, from_unit)
