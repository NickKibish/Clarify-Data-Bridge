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

_LOGGER = logging.getLogger(__name__)


class ClarifyDataCoordinator:
    """Coordinator for batching and sending data to Clarify.

    This coordinator accumulates state changes from Home Assistant entities
    and sends them in batches to Clarify at regular intervals.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        batch_interval: int = DEFAULT_BATCH_INTERVAL,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    ) -> None:
        """Initialize the data coordinator.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient instance for API communication.
            batch_interval: Interval in seconds between batch sends.
            max_batch_size: Maximum number of data points per batch.
        """
        self.hass = hass
        self.client = client
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size

        # Data buffer: {input_id: [(timestamp, value), ...]}
        self._data_buffer: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        self._buffer_lock = asyncio.Lock()

        # Track last send time for diagnostics
        self.last_send_time: datetime | None = None
        self.total_data_points_sent = 0
        self.failed_sends = 0

        # Timer for periodic sends
        self._unsub_timer = None

        _LOGGER.debug(
            "Initialized ClarifyDataCoordinator with batch_interval=%ds, max_batch_size=%d",
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
            self._async_send_batch,
            timedelta(seconds=self.batch_interval),
        )

    async def stop(self) -> None:
        """Stop the coordinator and send any remaining data."""
        _LOGGER.info("Stopping ClarifyDataCoordinator")

        # Cancel timer
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

        # Send any remaining data
        await self._async_send_batch(None)

    async def add_data_point(
        self,
        input_id: str,
        value: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Add a data point to the batch buffer.

        Args:
            input_id: Unique input ID for the signal.
            value: Numeric value to send.
            timestamp: Timestamp for the data point (defaults to now).
        """
        if timestamp is None:
            timestamp = dt_util.utcnow()

        async with self._buffer_lock:
            self._data_buffer[input_id].append((timestamp, value))
            buffer_size = sum(len(points) for points in self._data_buffer.values())

            _LOGGER.debug(
                "Added data point for %s: value=%.2f, timestamp=%s (buffer size: %d)",
                input_id,
                value,
                timestamp.isoformat(),
                buffer_size,
            )

            # If buffer exceeds max size, trigger immediate send
            if buffer_size >= self.max_batch_size:
                _LOGGER.info(
                    "Buffer size (%d) exceeds max (%d), triggering immediate send",
                    buffer_size,
                    self.max_batch_size,
                )
                await self._async_send_batch(None)

    async def _async_send_batch(self, now: datetime | None) -> None:
        """Send accumulated data to Clarify.

        Args:
            now: Current time (unused, required for time interval callback).
        """
        async with self._buffer_lock:
            if not self._data_buffer:
                _LOGGER.debug("No data to send, buffer is empty")
                return

            # Copy and clear buffer
            data_to_send = dict(self._data_buffer)
            self._data_buffer.clear()

        try:
            # Convert buffer to pyclarify DataFrame format
            dataframe = self._build_dataframe(data_to_send)

            if not dataframe.times:
                _LOGGER.debug("No valid data points to send")
                return

            # Send to Clarify
            _LOGGER.info(
                "Sending batch to Clarify: %d timestamps, %d series",
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

            _LOGGER.info(
                "Successfully sent batch: %d data points (total sent: %d)",
                data_points,
                self.total_data_points_sent,
            )

        except ClarifyConnectionError as err:
            self.failed_sends += 1
            _LOGGER.error("Failed to send batch to Clarify: %s", err)

            # Put data back in buffer for retry
            async with self._buffer_lock:
                for input_id, points in data_to_send.items():
                    self._data_buffer[input_id].extend(points)

            _LOGGER.warning(
                "Data returned to buffer for retry (failed sends: %d)",
                self.failed_sends,
            )

        except Exception as err:
            self.failed_sends += 1
            _LOGGER.exception("Unexpected error sending batch: %s", err)

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

    @property
    def buffer_size(self) -> int:
        """Get current buffer size (number of data points)."""
        return sum(len(points) for points in self._data_buffer.values())

    @property
    def buffer_signals(self) -> int:
        """Get number of signals in buffer."""
        return len(self._data_buffer)
