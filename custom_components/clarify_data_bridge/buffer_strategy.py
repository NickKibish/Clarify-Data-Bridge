"""Intelligent buffering strategies for data collection."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .entity_selector import DataPriority

_LOGGER = logging.getLogger(__name__)


class BufferStrategy(Enum):
    """Buffering strategy types."""

    TIME_BASED = "time"  # Flush every X seconds
    SIZE_BASED = "size"  # Flush when buffer reaches Y entries
    PRIORITY_BASED = "priority"  # Flush high-priority immediately, batch others
    HYBRID = "hybrid"  # Combination of time and size
    ADAPTIVE = "adaptive"  # Adjust based on data rate


class FlushTrigger(Enum):
    """Reason for buffer flush."""

    TIME_INTERVAL = "time_interval"  # Regular time interval reached
    SIZE_LIMIT = "size_limit"  # Buffer size limit reached
    PRIORITY = "priority"  # High priority data requires immediate send
    MANUAL = "manual"  # Manual flush requested
    SHUTDOWN = "shutdown"  # System shutdown
    ADAPTIVE = "adaptive"  # Adaptive strategy decision


@dataclass
class BufferEntry:
    """Single buffered data point."""

    input_id: str
    value: float
    timestamp: datetime
    priority: DataPriority = DataPriority.LOW
    entity_id: str | None = None
    device_class: str | None = None


@dataclass
class BufferMetrics:
    """Metrics for buffer performance."""

    total_entries: int = 0
    flushes: int = 0
    flush_triggers: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    avg_buffer_size: float = 0.0
    max_buffer_size: int = 0
    data_rate: float = 0.0  # Entries per second
    last_flush_time: datetime | None = None
    last_flush_size: int = 0


class BufferStrategyManager:
    """Manages buffering strategies for efficient data collection.

    Implements multiple buffering strategies:
    - Time-based: Flush every X seconds
    - Size-based: Flush when buffer reaches Y entries
    - Priority-based: Immediate flush for high-priority, batch others
    - Hybrid: Combination of time and size
    - Adaptive: Adjust flush frequency based on data rate
    """

    def __init__(
        self,
        strategy: BufferStrategy = BufferStrategy.HYBRID,
        time_interval: int = 300,  # 5 minutes
        size_limit: int = 100,
        priority_immediate: bool = True,
        priority_threshold: DataPriority = DataPriority.HIGH,
        adaptive_min_interval: int = 60,  # 1 minute
        adaptive_max_interval: int = 600,  # 10 minutes
    ) -> None:
        """Initialize buffer strategy manager.

        Args:
            strategy: Buffering strategy to use.
            time_interval: Flush interval in seconds for time-based strategy.
            size_limit: Maximum buffer size for size-based strategy.
            priority_immediate: Whether to flush high-priority data immediately.
            priority_threshold: Minimum priority for immediate flush.
            adaptive_min_interval: Minimum interval for adaptive strategy.
            adaptive_max_interval: Maximum interval for adaptive strategy.
        """
        self.strategy = strategy
        self.time_interval = time_interval
        self.size_limit = size_limit
        self.priority_immediate = priority_immediate
        self.priority_threshold = priority_threshold
        self.adaptive_min_interval = adaptive_min_interval
        self.adaptive_max_interval = adaptive_max_interval

        # Buffers separated by priority
        self._high_priority_buffer: list[BufferEntry] = []
        self._medium_priority_buffer: list[BufferEntry] = []
        self._low_priority_buffer: list[BufferEntry] = []

        # Timing
        self._last_flush_time = dt_util.utcnow()
        self._buffer_start_time = dt_util.utcnow()

        # Metrics
        self.metrics = BufferMetrics()

        # Adaptive strategy state
        self._entry_timestamps: list[datetime] = []
        self._current_interval = time_interval

        _LOGGER.info(
            "Initialized BufferStrategyManager: strategy=%s, time_interval=%ds, size_limit=%d",
            strategy.value,
            time_interval,
            size_limit,
        )

    def add_entry(self, entry: BufferEntry) -> FlushTrigger | None:
        """Add data point to buffer.

        Args:
            entry: Buffer entry to add.

        Returns:
            FlushTrigger if buffer should be flushed, None otherwise.
        """
        # Add to appropriate priority buffer
        if entry.priority == DataPriority.HIGH:
            self._high_priority_buffer.append(entry)
        elif entry.priority == DataPriority.MEDIUM:
            self._medium_priority_buffer.append(entry)
        else:
            self._low_priority_buffer.append(entry)

        # Update metrics
        self.metrics.total_entries += 1
        current_size = self.get_total_buffer_size()
        if current_size > self.metrics.max_buffer_size:
            self.metrics.max_buffer_size = current_size

        # Track entry timestamp for adaptive strategy
        if self.strategy == BufferStrategy.ADAPTIVE:
            self._entry_timestamps.append(entry.timestamp)
            # Keep only last 100 timestamps for rate calculation
            if len(self._entry_timestamps) > 100:
                self._entry_timestamps.pop(0)

        # Determine if flush is needed
        return self._should_flush(entry)

    def _should_flush(self, latest_entry: BufferEntry | None = None) -> FlushTrigger | None:
        """Determine if buffer should be flushed.

        Args:
            latest_entry: Most recent entry added (for priority check).

        Returns:
            FlushTrigger if flush needed, None otherwise.
        """
        # Priority-based immediate flush
        if (
            self.priority_immediate
            and latest_entry
            and latest_entry.priority.value >= self.priority_threshold.value
        ):
            _LOGGER.debug(
                "Priority flush triggered for %s (priority: %s)",
                latest_entry.entity_id,
                latest_entry.priority.name,
            )
            return FlushTrigger.PRIORITY

        total_size = self.get_total_buffer_size()

        # Strategy-specific checks
        if self.strategy == BufferStrategy.TIME_BASED:
            return self._check_time_based()

        elif self.strategy == BufferStrategy.SIZE_BASED:
            return self._check_size_based(total_size)

        elif self.strategy == BufferStrategy.PRIORITY_BASED:
            # For priority-based, we already checked priority above
            # Flush other priorities on size limit
            if total_size >= self.size_limit:
                return FlushTrigger.SIZE_LIMIT
            return None

        elif self.strategy == BufferStrategy.HYBRID:
            # Check both time and size
            time_trigger = self._check_time_based()
            if time_trigger:
                return time_trigger

            size_trigger = self._check_size_based(total_size)
            if size_trigger:
                return size_trigger

            return None

        elif self.strategy == BufferStrategy.ADAPTIVE:
            return self._check_adaptive(total_size)

        return None

    def _check_time_based(self) -> FlushTrigger | None:
        """Check if time-based flush is needed."""
        now = dt_util.utcnow()
        elapsed = (now - self._last_flush_time).total_seconds()

        if elapsed >= self.time_interval:
            _LOGGER.debug(
                "Time-based flush triggered (elapsed: %.1fs >= interval: %ds)",
                elapsed,
                self.time_interval,
            )
            return FlushTrigger.TIME_INTERVAL

        return None

    def _check_size_based(self, total_size: int) -> FlushTrigger | None:
        """Check if size-based flush is needed."""
        if total_size >= self.size_limit:
            _LOGGER.debug(
                "Size-based flush triggered (size: %d >= limit: %d)",
                total_size,
                self.size_limit,
            )
            return FlushTrigger.SIZE_LIMIT

        return None

    def _check_adaptive(self, total_size: int) -> FlushTrigger | None:
        """Check if adaptive flush is needed.

        Adapts flush interval based on data rate:
        - High data rate: Flush more frequently
        - Low data rate: Flush less frequently
        """
        # Calculate current data rate
        if len(self._entry_timestamps) < 2:
            return None

        time_span = (
            self._entry_timestamps[-1] - self._entry_timestamps[0]
        ).total_seconds()

        if time_span > 0:
            data_rate = len(self._entry_timestamps) / time_span
            self.metrics.data_rate = data_rate

            # Adjust interval based on data rate
            # High rate (>1/sec): Use minimum interval
            # Low rate (<0.1/sec): Use maximum interval
            if data_rate > 1.0:
                self._current_interval = self.adaptive_min_interval
            elif data_rate < 0.1:
                self._current_interval = self.adaptive_max_interval
            else:
                # Linear interpolation
                rate_factor = (data_rate - 0.1) / 0.9
                interval_range = self.adaptive_max_interval - self.adaptive_min_interval
                self._current_interval = int(
                    self.adaptive_max_interval - (rate_factor * interval_range)
                )

            _LOGGER.debug(
                "Adaptive strategy: rate=%.2f entries/sec, interval=%ds",
                data_rate,
                self._current_interval,
            )

        # Check if current interval has passed
        now = dt_util.utcnow()
        elapsed = (now - self._last_flush_time).total_seconds()

        if elapsed >= self._current_interval:
            return FlushTrigger.ADAPTIVE

        # Also check size limit
        if total_size >= self.size_limit:
            return FlushTrigger.SIZE_LIMIT

        return None

    def get_flush_data(
        self,
        trigger: FlushTrigger,
    ) -> dict[str, list[BufferEntry]]:
        """Get data to flush based on trigger.

        Args:
            trigger: Flush trigger type.

        Returns:
            Dictionary mapping priority level to list of entries.
        """
        data: dict[str, list[BufferEntry]] = {}

        # For priority triggers, only flush high-priority buffer
        if trigger == FlushTrigger.PRIORITY:
            if self._high_priority_buffer:
                data["high"] = self._high_priority_buffer.copy()
                self._high_priority_buffer.clear()

        # For other triggers, flush all buffers
        else:
            if self._high_priority_buffer:
                data["high"] = self._high_priority_buffer.copy()
                self._high_priority_buffer.clear()

            if self._medium_priority_buffer:
                data["medium"] = self._medium_priority_buffer.copy()
                self._medium_priority_buffer.clear()

            if self._low_priority_buffer:
                data["low"] = self._low_priority_buffer.copy()
                self._low_priority_buffer.clear()

        # Update metrics
        total_flushed = sum(len(entries) for entries in data.values())
        self.metrics.flushes += 1
        self.metrics.flush_triggers[trigger.value] += 1
        self.metrics.last_flush_time = dt_util.utcnow()
        self.metrics.last_flush_size = total_flushed

        # Update average buffer size
        if self.metrics.flushes > 0:
            self.metrics.avg_buffer_size = (
                (self.metrics.avg_buffer_size * (self.metrics.flushes - 1) + total_flushed)
                / self.metrics.flushes
            )

        self._last_flush_time = dt_util.utcnow()

        _LOGGER.info(
            "Flushing buffer: trigger=%s, total_entries=%d, priorities=%s",
            trigger.value,
            total_flushed,
            {k: len(v) for k, v in data.items()},
        )

        return data

    def get_total_buffer_size(self) -> int:
        """Get total number of entries across all buffers."""
        return (
            len(self._high_priority_buffer)
            + len(self._medium_priority_buffer)
            + len(self._low_priority_buffer)
        )

    def get_buffer_sizes(self) -> dict[str, int]:
        """Get buffer sizes by priority."""
        return {
            "high": len(self._high_priority_buffer),
            "medium": len(self._medium_priority_buffer),
            "low": len(self._low_priority_buffer),
            "total": self.get_total_buffer_size(),
        }

    def manual_flush(self) -> dict[str, list[BufferEntry]]:
        """Manually trigger a buffer flush.

        Returns:
            Dictionary mapping priority level to list of entries.
        """
        return self.get_flush_data(FlushTrigger.MANUAL)

    def shutdown_flush(self) -> dict[str, list[BufferEntry]]:
        """Flush all buffers on shutdown.

        Returns:
            Dictionary mapping priority level to list of entries.
        """
        return self.get_flush_data(FlushTrigger.SHUTDOWN)

    def get_metrics(self) -> dict[str, Any]:
        """Get buffer metrics.

        Returns:
            Dictionary of metrics.
        """
        return {
            "total_entries": self.metrics.total_entries,
            "flushes": self.metrics.flushes,
            "flush_triggers": dict(self.metrics.flush_triggers),
            "avg_buffer_size": round(self.metrics.avg_buffer_size, 2),
            "max_buffer_size": self.metrics.max_buffer_size,
            "current_buffer_size": self.get_total_buffer_size(),
            "buffer_sizes": self.get_buffer_sizes(),
            "data_rate": round(self.metrics.data_rate, 3),
            "last_flush_time": (
                self.metrics.last_flush_time.isoformat()
                if self.metrics.last_flush_time
                else None
            ),
            "last_flush_size": self.metrics.last_flush_size,
            "strategy": self.strategy.value,
            "time_interval": self.time_interval,
            "size_limit": self.size_limit,
        }

    def reset_metrics(self) -> None:
        """Reset buffer metrics."""
        self.metrics = BufferMetrics()


class PriorityQueue:
    """Priority queue for managing entity updates by priority.

    Separates high, medium, and low priority entities for
    optimized processing and buffering.
    """

    def __init__(self) -> None:
        """Initialize priority queue."""
        self._queues: dict[DataPriority, list[BufferEntry]] = {
            DataPriority.HIGH: [],
            DataPriority.MEDIUM: [],
            DataPriority.LOW: [],
        }

        # Track queue sizes over time
        self._queue_stats: dict[DataPriority, dict[str, int]] = {
            priority: {"total_added": 0, "total_removed": 0, "max_size": 0}
            for priority in DataPriority
        }

    def add(self, entry: BufferEntry) -> None:
        """Add entry to appropriate priority queue.

        Args:
            entry: Buffer entry to add.
        """
        priority = entry.priority
        self._queues[priority].append(entry)

        # Update stats
        self._queue_stats[priority]["total_added"] += 1
        current_size = len(self._queues[priority])
        if current_size > self._queue_stats[priority]["max_size"]:
            self._queue_stats[priority]["max_size"] = current_size

    def get_high_priority(self, limit: int | None = None) -> list[BufferEntry]:
        """Get high-priority entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of high-priority entries.
        """
        return self._get_entries(DataPriority.HIGH, limit)

    def get_medium_priority(self, limit: int | None = None) -> list[BufferEntry]:
        """Get medium-priority entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of medium-priority entries.
        """
        return self._get_entries(DataPriority.MEDIUM, limit)

    def get_low_priority(self, limit: int | None = None) -> list[BufferEntry]:
        """Get low-priority entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of low-priority entries.
        """
        return self._get_entries(DataPriority.LOW, limit)

    def get_all(self, limit: int | None = None) -> list[BufferEntry]:
        """Get all entries (high priority first).

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of all entries, sorted by priority.
        """
        all_entries = []

        # Add high priority first
        all_entries.extend(self._queues[DataPriority.HIGH])

        # Then medium
        all_entries.extend(self._queues[DataPriority.MEDIUM])

        # Then low
        all_entries.extend(self._queues[DataPriority.LOW])

        if limit:
            return all_entries[:limit]

        return all_entries

    def _get_entries(
        self,
        priority: DataPriority,
        limit: int | None = None,
    ) -> list[BufferEntry]:
        """Get entries from specific priority queue.

        Args:
            priority: Priority level.
            limit: Maximum number to return.

        Returns:
            List of entries.
        """
        queue = self._queues[priority]

        if limit is None or limit >= len(queue):
            entries = queue.copy()
            queue.clear()
        else:
            entries = queue[:limit]
            del queue[:limit]

        # Update stats
        self._queue_stats[priority]["total_removed"] += len(entries)

        return entries

    def clear_all(self) -> None:
        """Clear all queues."""
        for queue in self._queues.values():
            queue.clear()

    def get_sizes(self) -> dict[str, int]:
        """Get current queue sizes.

        Returns:
            Dictionary mapping priority names to sizes.
        """
        return {
            priority.name: len(queue)
            for priority, queue in self._queues.items()
        }

    def get_total_size(self) -> int:
        """Get total entries across all queues."""
        return sum(len(queue) for queue in self._queues.values())

    def get_statistics(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dictionary of statistics.
        """
        return {
            "current_sizes": self.get_sizes(),
            "total_size": self.get_total_size(),
            "stats_by_priority": {
                priority.name: stats
                for priority, stats in self._queue_stats.items()
            },
        }
