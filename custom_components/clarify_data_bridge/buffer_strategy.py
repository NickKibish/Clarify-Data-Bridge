"""Intelligent buffering strategies for data collection."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class BufferStrategy(Enum):
    """Buffering strategy types."""

    TIME_BASED = "time"  # Flush every X seconds
    SIZE_BASED = "size"  # Flush when buffer reaches Y entries
    HYBRID = "hybrid"  # Combination of time and size
    ADAPTIVE = "adaptive"  # Adjust based on data rate


class FlushTrigger(Enum):
    """Reason for buffer flush."""

    TIME_INTERVAL = "time_interval"  # Regular time interval reached
    SIZE_LIMIT = "size_limit"  # Buffer size limit reached
    MANUAL = "manual"  # Manual flush requested
    SHUTDOWN = "shutdown"  # System shutdown
    ADAPTIVE = "adaptive"  # Adaptive strategy decision


@dataclass
class BufferEntry:
    """Single buffered data point."""

    input_id: str
    value: float
    timestamp: datetime
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
    - Hybrid: Combination of time and size
    - Adaptive: Adjust flush frequency based on data rate
    """

    def __init__(
        self,
        strategy: BufferStrategy = BufferStrategy.HYBRID,
        time_interval: int = 300,  # 5 minutes
        size_limit: int = 100,
        adaptive_min_interval: int = 60,  # 1 minute
        adaptive_max_interval: int = 600,  # 10 minutes
    ) -> None:
        """Initialize buffer strategy manager.

        Args:
            strategy: Buffering strategy to use.
            time_interval: Flush interval in seconds for time-based strategy.
            size_limit: Maximum buffer size for size-based strategy.
            adaptive_min_interval: Minimum interval for adaptive strategy.
            adaptive_max_interval: Maximum interval for adaptive strategy.
        """
        self.strategy = strategy
        self.time_interval = time_interval
        self.size_limit = size_limit
        self.adaptive_min_interval = adaptive_min_interval
        self.adaptive_max_interval = adaptive_max_interval

        # Unified buffer for all entries
        self._buffer: list[BufferEntry] = []

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
        # Add to unified buffer
        self._buffer.append(entry)

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
        return self._should_flush()

    def _should_flush(self) -> FlushTrigger | None:
        """Determine if buffer should be flushed.

        Returns:
            FlushTrigger if flush needed, None otherwise.
        """
        total_size = self.get_total_buffer_size()

        # Strategy-specific checks
        if self.strategy == BufferStrategy.TIME_BASED:
            return self._check_time_based()

        elif self.strategy == BufferStrategy.SIZE_BASED:
            return self._check_size_based(total_size)

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
    ) -> list[BufferEntry]:
        """Get data to flush based on trigger.

        Args:
            trigger: Flush trigger type.

        Returns:
            List of buffer entries.
        """
        # Get all entries from unified buffer
        data = self._buffer.copy()
        self._buffer.clear()

        # Update metrics
        total_flushed = len(data)
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
            "Flushing buffer: trigger=%s, total_entries=%d",
            trigger.value,
            total_flushed,
        )

        return data

    def get_total_buffer_size(self) -> int:
        """Get total number of entries in buffer."""
        return len(self._buffer)

    def get_buffer_sizes(self) -> dict[str, int]:
        """Get buffer size info."""
        return {
            "total": self.get_total_buffer_size(),
        }

    def manual_flush(self) -> list[BufferEntry]:
        """Manually trigger a buffer flush.

        Returns:
            List of buffer entries.
        """
        return self.get_flush_data(FlushTrigger.MANUAL)

    def shutdown_flush(self) -> list[BufferEntry]:
        """Flush all buffers on shutdown.

        Returns:
            List of buffer entries.
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
