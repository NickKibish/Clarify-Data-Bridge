"""Data coordinator for batching and sending data to Clarify."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from pyclarify import DataFrame

from .clarify_client import ClarifyClient, ClarifyConnectionError
from .const import DEFAULT_BATCH_INTERVAL, DEFAULT_MAX_BATCH_SIZE
from .buffer_strategy import (
    BufferStrategy,
    BufferStrategyManager,
    BufferEntry,
    FlushTrigger,
)

_LOGGER = logging.getLogger(__name__)


class ClarifyDataCoordinator:
    """Coordinator for batching and sending data to Clarify.

    This coordinator accumulates state changes from Home Assistant entities
    and sends them in batches to Clarify using intelligent buffering strategies.

    Supports multiple buffering strategies:
    - Time-based: Flush every X seconds
    - Size-based: Flush when buffer reaches Y entries
    - Hybrid: Combination of time and size
    - Adaptive: Adjust based on data rate
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        batch_interval: int = DEFAULT_BATCH_INTERVAL,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        buffer_strategy: BufferStrategy = BufferStrategy.HYBRID,
    ) -> None:
        """Initialize the data coordinator.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient instance for API communication.
            batch_interval: Interval in seconds between batch sends.
            max_batch_size: Maximum number of data points per batch.
            buffer_strategy: Buffering strategy to use.
        """
        self.hass = hass
        self.client = client
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size

        # Initialize buffer strategy manager
        self.buffer_manager = BufferStrategyManager(
            strategy=buffer_strategy,
            time_interval=batch_interval,
            size_limit=max_batch_size,
        )

        # Legacy buffer for backward compatibility (simple dict backup)
        self._data_buffer: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        self._buffer_lock = asyncio.Lock()

        # Track last send time for diagnostics
        self.last_send_time: datetime | None = None
        self.total_data_points_sent = 0
        self.failed_sends = 0
        self.successful_sends = 0

        # Timer for periodic sends
        self._unsub_timer = None
        self._check_timer = None

        _LOGGER.info(
            "Initialized ClarifyDataCoordinator: strategy=%s, interval=%ds, max_size=%d",
            buffer_strategy.value,
            batch_interval,
            max_batch_size,
        )

    async def start(self) -> None:
        """Start the coordinator and begin periodic batch sends."""
        if self._unsub_timer is not None:
            _LOGGER.warning("Coordinator already started")
            return

        _LOGGER.info("Starting ClarifyDataCoordinator")

        # Schedule periodic batch sends
        self._unsub_timer = async_track_time_interval(
            self.hass,
            self._async_periodic_check,
            timedelta(seconds=self.batch_interval),
        )

        # Schedule more frequent buffer checks (every 10 seconds)
        self._check_timer = async_track_time_interval(
            self.hass,
            self._async_check_buffer,
            timedelta(seconds=10),
        )

    async def stop(self) -> None:
        """Stop the coordinator and send any remaining data."""
        _LOGGER.info("Stopping ClarifyDataCoordinator")

        # Cancel timers
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

        if self._check_timer is not None:
            self._check_timer()
            self._check_timer = None

        # Send any remaining data
        await self._async_flush_buffer(FlushTrigger.SHUTDOWN)

    async def add_data_point(
        self,
        input_id: str,
        value: float,
        timestamp: datetime | None = None,
        entity_id: str | None = None,
        device_class: str | None = None,
    ) -> None:
        """Add a data point to the batch buffer.

        Args:
            input_id: Unique input ID for the signal.
            value: Numeric value to send.
            timestamp: Timestamp for the data point (defaults to now).
            entity_id: Entity ID (for logging/metrics).
            device_class: Device class (for logging/metrics).
        """
        if timestamp is None:
            timestamp = dt_util.utcnow()

        # Create buffer entry
        entry = BufferEntry(
            input_id=input_id,
            value=value,
            timestamp=timestamp,
            entity_id=entity_id,
            device_class=device_class,
        )

        async with self._buffer_lock:
            # Add to buffer manager
            flush_trigger = self.buffer_manager.add_entry(entry)

            # Also add to legacy buffer
            self._data_buffer[input_id].append((timestamp, value))

            buffer_stats = self.buffer_manager.get_buffer_sizes()
            _LOGGER.info(
                "✓ Added data point to buffer: %s=%.2f (total_buffer=%d)",
                input_id,
                value,
                buffer_stats["total"],
            )

            # Check if immediate flush is needed
            if flush_trigger:
                _LOGGER.info(
                    "⚡ Flush triggered: %s (buffer size: %d)",
                    flush_trigger.value,
                    buffer_stats["total"],
                )
                await self._async_flush_buffer(flush_trigger)

    async def _async_periodic_check(self, now: datetime | None) -> None:
        """Periodic check for time-based flushing.

        Args:
            now: Current time (from timer callback).
        """
        await self._async_check_buffer(now)

    async def _async_check_buffer(self, now: datetime | None) -> None:
        """Check if buffer should be flushed.

        Args:
            now: Current time (from timer callback).
        """
        async with self._buffer_lock:
            # Let buffer manager determine if flush is needed
            flush_trigger = self.buffer_manager._should_flush()

            if flush_trigger:
                _LOGGER.debug("Buffer check triggered flush: %s", flush_trigger.value)
                await self._async_flush_buffer(flush_trigger)

    async def _async_flush_buffer(self, trigger: FlushTrigger) -> None:
        """Flush buffer based on trigger.

        Args:
            trigger: Flush trigger type.
        """
        _LOGGER.info("Attempting buffer flush (trigger=%s)", trigger.value)

        # Get current buffer stats before flush
        buffer_stats = self.buffer_manager.get_buffer_sizes()
        _LOGGER.info("Buffer state before flush: total=%d",
                    buffer_stats.get("total", 0))

        # Get data from buffer manager
        buffer_data = self.buffer_manager.get_flush_data(trigger)

        if not buffer_data:
            _LOGGER.warning("⚠ No data to flush for trigger: %s (buffer was empty!)", trigger.value)
            return

        # Convert buffer entries to dataframe format
        data_to_send: dict[str, list[tuple[datetime, float]]] = defaultdict(list)

        for entry in buffer_data:
            data_to_send[entry.input_id].append((entry.timestamp, entry.value))

        # Also include any data from legacy buffer
        if self._data_buffer:
            for input_id, points in self._data_buffer.items():
                data_to_send[input_id].extend(points)
            self._data_buffer.clear()

        if not data_to_send:
            _LOGGER.debug("No data to send after buffer conversion")
            return

        # Send data
        await self._async_send_data(data_to_send, trigger)

    async def _async_send_data(
        self,
        data: dict[str, list[tuple[datetime, float]]],
        trigger: FlushTrigger,
    ) -> None:
        """Send data to Clarify.

        Args:
            data: Data to send.
            trigger: Flush trigger (for logging).
        """
        try:
            # Convert buffer to pyclarify DataFrame format
            dataframe = self._build_dataframe(data)

            if not dataframe.times:
                _LOGGER.debug("No valid data points to send")
                return

            # Send to Clarify
            _LOGGER.info(
                "Sending batch to Clarify (trigger=%s): %d timestamps, %d series",
                trigger.value,
                len(dataframe.times),
                len(dataframe.series),
            )

            await self.client.async_insert_dataframe(dataframe)

            # Update statistics
            self.last_send_time = dt_util.utcnow()
            data_points = sum(
                len([v for v in series if v is not None])
                for series in dataframe.series.values()
            )
            self.total_data_points_sent += data_points
            self.successful_sends += 1

            _LOGGER.info(
                "Successfully sent batch: %d data points (total sent: %d, successful: %d)",
                data_points,
                self.total_data_points_sent,
                self.successful_sends,
            )

        except ClarifyConnectionError as err:
            self.failed_sends += 1
            _LOGGER.error("Failed to send batch to Clarify: %s", err)

            # Put data back in buffer for retry
            async with self._buffer_lock:
                for input_id, points in data.items():
                    self._data_buffer[input_id].extend(points)

            _LOGGER.warning(
                "Data returned to buffer for retry (failed sends: %d)",
                self.failed_sends,
            )

        except Exception as err:
            self.failed_sends += 1
            _LOGGER.exception("Unexpected error sending batch: %s", err)

    async def _async_send_batch(self, now: datetime | None) -> None:
        """Legacy method for compatibility. Redirects to buffer check.

        Args:
            now: Current time (unused, required for time interval callback).
        """
        await self._async_check_buffer(now)

    def _build_dataframe(
        self, data: dict[str, list[tuple[datetime, float]]]
    ) -> DataFrame:
        """Build a pyclarify DataFrame from buffered data.

        Args:
            data: Dictionary mapping input_ids to list of (timestamp, value) tuples.

        Returns:
            DataFrame ready for insertion to Clarify.
        """
        # Collect all unique timestamps
        all_timestamps: set[datetime] = set()
        for points in data.values():
            for timestamp, _ in points:
                all_timestamps.add(timestamp)

        # Sort timestamps
        sorted_timestamps = sorted(all_timestamps)

        # Build series data with None for missing values
        series_data: dict[str, list[float | None]] = {}

        for input_id, points in data.items():
            # Create a mapping of timestamp -> value for this input_id
            value_map = {timestamp: value for timestamp, value in points}

            # Build series with None for missing timestamps
            series_values = [
                value_map.get(ts) for ts in sorted_timestamps
            ]

            series_data[input_id] = series_values

        # Convert timestamps to ISO 8601 strings (Clarify format)
        time_strings = [ts.isoformat() for ts in sorted_timestamps]

        # Create DataFrame
        dataframe = DataFrame(
            times=time_strings,
            series=series_data,
        )

        return dataframe

    async def manual_flush(self) -> None:
        """Manually trigger a buffer flush."""
        async with self._buffer_lock:
            await self._async_flush_buffer(FlushTrigger.MANUAL)

    def get_statistics(self) -> dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Dictionary of statistics.
        """
        buffer_metrics = self.buffer_manager.get_metrics()

        return {
            "total_data_points_sent": self.total_data_points_sent,
            "successful_sends": self.successful_sends,
            "failed_sends": self.failed_sends,
            "last_send_time": (
                self.last_send_time.isoformat() if self.last_send_time else None
            ),
            "buffer_strategy": self.buffer_manager.strategy.value,
            "buffer_metrics": buffer_metrics,
            "legacy_buffer_size": self.buffer_size,
            "legacy_buffer_signals": self.buffer_signals,
        }

    @property
    def buffer_size(self) -> int:
        """Get current buffer size (number of data points)."""
        return sum(len(points) for points in self._data_buffer.values())

    @property
    def buffer_signals(self) -> int:
        """Get number of signals in buffer."""
        return len(self._data_buffer)
