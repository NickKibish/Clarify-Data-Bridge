"""Data aggregation for reducing transmission volume."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
import logging
from statistics import mean, median
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class AggregationMethod(Enum):
    """Data aggregation methods."""

    NONE = "none"
    AVERAGE = "average"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    FIRST = "first"
    LAST = "last"
    COUNT = "count"
    CHANGE_ONLY = "change_only"  # Only send if value changed


class DataAggregator:
    """Aggregates data points before transmission.

    Reduces data volume for high-frequency sensors by aggregating
    values over time windows.
    """

    def __init__(
        self,
        window_seconds: int = 300,
        method: AggregationMethod = AggregationMethod.AVERAGE,
        min_change_threshold: float | None = None,
    ) -> None:
        """Initialize data aggregator.

        Args:
            window_seconds: Aggregation window in seconds.
            method: Aggregation method to use.
            min_change_threshold: Minimum change to report (for CHANGE_ONLY).
        """
        self.window_seconds = window_seconds
        self.method = method
        self.min_change_threshold = min_change_threshold

        # Buffer: {entity_id: [(timestamp, value), ...]}
        self._data_buffer: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

        # Last reported values for change detection
        self._last_values: dict[str, float] = {}

        # Statistics
        self.total_points_received = 0
        self.total_points_aggregated = 0
        self.reduction_ratio = 0.0

        _LOGGER.debug(
            "Initialized DataAggregator: window=%ds, method=%s",
            window_seconds,
            method.value,
        )

    def add_data_point(
        self,
        entity_id: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """Add data point to aggregation buffer.

        Args:
            entity_id: Entity ID.
            value: Numeric value.
            timestamp: Timestamp of value.
        """
        self._data_buffer[entity_id].append((timestamp, value))
        self.total_points_received += 1

        # Clean old data
        self._clean_old_data(entity_id, timestamp)

    def _clean_old_data(self, entity_id: str, current_time: datetime) -> None:
        """Remove data points outside aggregation window.

        Args:
            entity_id: Entity ID.
            current_time: Current timestamp.
        """
        cutoff_time = current_time - timedelta(seconds=self.window_seconds * 2)

        # Keep only recent data
        self._data_buffer[entity_id] = [
            (ts, val)
            for ts, val in self._data_buffer[entity_id]
            if ts > cutoff_time
        ]

    def get_aggregated_value(
        self,
        entity_id: str,
        window_end: datetime | None = None,
    ) -> tuple[float | None, datetime | None]:
        """Get aggregated value for entity.

        Args:
            entity_id: Entity ID.
            window_end: End of aggregation window (defaults to now).

        Returns:
            Tuple of (aggregated_value, window_end_time) or (None, None).
        """
        if entity_id not in self._data_buffer or not self._data_buffer[entity_id]:
            return None, None

        if window_end is None:
            window_end = dt_util.utcnow()

        window_start = window_end - timedelta(seconds=self.window_seconds)

        # Filter data points in window
        window_data = [
            (ts, val)
            for ts, val in self._data_buffer[entity_id]
            if window_start <= ts <= window_end
        ]

        if not window_data:
            return None, None

        values = [val for _, val in window_data]

        # Apply aggregation method
        if self.method == AggregationMethod.NONE:
            # Return all values (no aggregation)
            return None, None

        elif self.method == AggregationMethod.AVERAGE:
            aggregated = mean(values)

        elif self.method == AggregationMethod.MEDIAN:
            aggregated = median(values)

        elif self.method == AggregationMethod.MIN:
            aggregated = min(values)

        elif self.method == AggregationMethod.MAX:
            aggregated = max(values)

        elif self.method == AggregationMethod.SUM:
            aggregated = sum(values)

        elif self.method == AggregationMethod.FIRST:
            aggregated = values[0]

        elif self.method == AggregationMethod.LAST:
            aggregated = values[-1]

        elif self.method == AggregationMethod.COUNT:
            aggregated = float(len(values))

        elif self.method == AggregationMethod.CHANGE_ONLY:
            # Check if value changed significantly
            last_value = self._last_values.get(entity_id)
            current_value = values[-1]

            if last_value is None:
                # First value, report it
                self._last_values[entity_id] = current_value
                aggregated = current_value
            else:
                # Check change threshold
                if self.min_change_threshold is not None:
                    change = abs(current_value - last_value)
                    if change >= self.min_change_threshold:
                        self._last_values[entity_id] = current_value
                        aggregated = current_value
                    else:
                        # No significant change
                        return None, None
                else:
                    # Simple change detection
                    if current_value != last_value:
                        self._last_values[entity_id] = current_value
                        aggregated = current_value
                    else:
                        return None, None

        else:
            _LOGGER.warning("Unknown aggregation method: %s", self.method)
            return None, None

        self.total_points_aggregated += 1

        # Update reduction ratio
        if self.total_points_received > 0:
            self.reduction_ratio = (
                1 - (self.total_points_aggregated / self.total_points_received)
            ) * 100

        _LOGGER.debug(
            "Aggregated %d points for %s: %.2f (method=%s)",
            len(values),
            entity_id,
            aggregated,
            self.method.value,
        )

        return aggregated, window_end

    def flush_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Flush aggregated data for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Dictionary with aggregated value and metadata, or None.
        """
        aggregated_value, timestamp = self.get_aggregated_value(entity_id)

        if aggregated_value is None:
            return None

        # Get original data count
        original_count = len(self._data_buffer.get(entity_id, []))

        # Clear buffer for this entity
        self._data_buffer[entity_id] = []

        return {
            "entity_id": entity_id,
            "value": aggregated_value,
            "timestamp": timestamp,
            "method": self.method.value,
            "window_seconds": self.window_seconds,
            "original_data_points": original_count,
        }

    def flush_all(self) -> dict[str, dict[str, Any]]:
        """Flush all aggregated data.

        Returns:
            Dictionary mapping entity_id to aggregated data.
        """
        results = {}

        for entity_id in list(self._data_buffer.keys()):
            result = self.flush_entity(entity_id)
            if result:
                results[entity_id] = result

        return results

    def get_buffer_stats(self) -> dict[str, Any]:
        """Get aggregation buffer statistics.

        Returns:
            Dictionary with buffer statistics.
        """
        total_buffered = sum(len(points) for points in self._data_buffer.values())

        return {
            "total_points_received": self.total_points_received,
            "total_points_aggregated": self.total_points_aggregated,
            "reduction_ratio_percent": round(self.reduction_ratio, 2),
            "entities_buffered": len(self._data_buffer),
            "total_buffered_points": total_buffered,
            "aggregation_method": self.method.value,
            "window_seconds": self.window_seconds,
        }


class EntityAggregatorManager:
    """Manages per-entity aggregation configurations."""

    def __init__(self) -> None:
        """Initialize entity aggregator manager."""
        # Per-entity aggregators
        self._aggregators: dict[str, DataAggregator] = {}

        # Default configuration
        self._default_window = 300
        self._default_method = AggregationMethod.NONE

        _LOGGER.debug("Initialized EntityAggregatorManager")

    def configure_entity(
        self,
        entity_id: str,
        window_seconds: int,
        method: AggregationMethod,
        min_change_threshold: float | None = None,
    ) -> None:
        """Configure aggregation for specific entity.

        Args:
            entity_id: Entity ID.
            window_seconds: Aggregation window in seconds.
            method: Aggregation method.
            min_change_threshold: Minimum change threshold.
        """
        aggregator = DataAggregator(
            window_seconds=window_seconds,
            method=method,
            min_change_threshold=min_change_threshold,
        )

        self._aggregators[entity_id] = aggregator

        _LOGGER.info(
            "Configured aggregation for %s: method=%s, window=%ds",
            entity_id,
            method.value,
            window_seconds,
        )

    def add_data_point(
        self,
        entity_id: str,
        value: float,
        timestamp: datetime,
    ) -> None:
        """Add data point to appropriate aggregator.

        Args:
            entity_id: Entity ID.
            value: Numeric value.
            timestamp: Timestamp.
        """
        if entity_id in self._aggregators:
            self._aggregators[entity_id].add_data_point(entity_id, value, timestamp)
        # If no aggregator configured, data passes through without aggregation

    def get_aggregated_value(
        self,
        entity_id: str,
    ) -> tuple[float | None, datetime | None]:
        """Get aggregated value for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Tuple of (value, timestamp) or (None, None).
        """
        if entity_id in self._aggregators:
            return self._aggregators[entity_id].get_aggregated_value(entity_id)
        return None, None

    def flush_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Flush aggregated data for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            Aggregated data dictionary or None.
        """
        if entity_id in self._aggregators:
            return self._aggregators[entity_id].flush_entity(entity_id)
        return None

    def flush_all(self) -> dict[str, dict[str, Any]]:
        """Flush all aggregated data.

        Returns:
            Dictionary mapping entity_ids to aggregated data.
        """
        results = {}

        for entity_id, aggregator in self._aggregators.items():
            result = aggregator.flush_entity(entity_id)
            if result:
                results[entity_id] = result

        return results

    def is_aggregation_enabled(self, entity_id: str) -> bool:
        """Check if aggregation is enabled for entity.

        Args:
            entity_id: Entity ID.

        Returns:
            True if aggregation is configured.
        """
        return entity_id in self._aggregators

    def get_aggregation_stats(self) -> dict[str, Any]:
        """Get aggregation statistics.

        Returns:
            Dictionary with aggregation statistics.
        """
        total_received = sum(
            agg.total_points_received for agg in self._aggregators.values()
        )
        total_aggregated = sum(
            agg.total_points_aggregated for agg in self._aggregators.values()
        )

        reduction_ratio = 0.0
        if total_received > 0:
            reduction_ratio = (1 - (total_aggregated / total_received)) * 100

        return {
            "entities_with_aggregation": len(self._aggregators),
            "total_points_received": total_received,
            "total_points_aggregated": total_aggregated,
            "reduction_ratio_percent": round(reduction_ratio, 2),
            "by_entity": {
                entity_id: aggregator.get_buffer_stats()
                for entity_id, aggregator in self._aggregators.items()
            },
        }
