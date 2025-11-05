"""Historical data synchronization from Home Assistant recorder to Clarify.io."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.components import recorder
from homeassistant.components.recorder import get_instance, history
from pyclarify import DataFrame

_LOGGER = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of historical sync operation."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HistoricalDataSync:
    """Synchronize historical data from Home Assistant to Clarify.io.

    Exports historical data from recorder database to Clarify.io
    in manageable batches to avoid overwhelming either system.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: Any,  # ClarifyClient
        signal_manager: Any,  # ClarifySignalManager
        batch_size: int = 500,
        batch_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize historical data sync.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient for API calls.
            signal_manager: Signal manager for entity mapping.
            batch_size: Number of data points per batch.
            batch_interval_seconds: Delay between batches.
        """
        self.hass = hass
        self.client = client
        self.signal_manager = signal_manager
        self.batch_size = batch_size
        self.batch_interval_seconds = batch_interval_seconds

        # Sync state
        self._status = SyncStatus.NOT_STARTED
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None
        self._sync_start_timestamp: datetime | None = None
        self._sync_end_timestamp: datetime | None = None

        # Statistics
        self._total_entities = 0
        self._processed_entities = 0
        self._total_data_points = 0
        self._sent_data_points = 0
        self._batches_sent = 0
        self._failed_batches = 0
        self._current_entity = ""

        # Cancellation
        self._cancel_requested = False

        _LOGGER.debug(
            "Initialized HistoricalDataSync: batch_size=%d, batch_interval=%.1fs",
            batch_size,
            batch_interval_seconds,
        )

    async def async_sync_historical_data(
        self,
        entity_ids: list[str],
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Synchronize historical data for entities.

        Args:
            entity_ids: List of entity IDs to sync.
            start_time: Start of time range to sync.
            end_time: End of time range (defaults to now).

        Returns:
            Dictionary with sync results.
        """
        if self._status == SyncStatus.IN_PROGRESS:
            raise ValueError("Historical sync already in progress")

        if end_time is None:
            end_time = dt_util.utcnow()

        # Validate time range
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Check if recorder is available
        if not recorder.is_entity_recorded(self.hass, entity_ids[0] if entity_ids else "sensor.test"):
            _LOGGER.warning("Recorder component not available, cannot sync historical data")
            return {
                "status": "failed",
                "error": "Recorder component not available",
            }

        # Initialize sync
        self._status = SyncStatus.IN_PROGRESS
        self._start_time = dt_util.utcnow()
        self._sync_start_timestamp = start_time
        self._sync_end_timestamp = end_time
        self._total_entities = len(entity_ids)
        self._processed_entities = 0
        self._total_data_points = 0
        self._sent_data_points = 0
        self._batches_sent = 0
        self._failed_batches = 0
        self._cancel_requested = False

        _LOGGER.info(
            "Starting historical data sync: %d entities, %s to %s",
            len(entity_ids),
            start_time.isoformat(),
            end_time.isoformat(),
        )

        try:
            # Process entities in batches
            for entity_id in entity_ids:
                if self._cancel_requested:
                    _LOGGER.warning("Historical sync cancelled")
                    self._status = SyncStatus.CANCELLED
                    break

                self._current_entity = entity_id

                # Get historical data for entity
                await self._async_sync_entity_history(
                    entity_id,
                    start_time,
                    end_time,
                )

                self._processed_entities += 1

                # Log progress
                progress = (self._processed_entities / self._total_entities) * 100
                _LOGGER.info(
                    "Historical sync progress: %.1f%% (%d/%d entities), %d points sent",
                    progress,
                    self._processed_entities,
                    self._total_entities,
                    self._sent_data_points,
                )

            # Mark as completed
            if not self._cancel_requested:
                self._status = SyncStatus.COMPLETED

            self._end_time = dt_util.utcnow()

            result = {
                "status": self._status.value,
                "total_entities": self._total_entities,
                "processed_entities": self._processed_entities,
                "total_data_points": self._total_data_points,
                "sent_data_points": self._sent_data_points,
                "batches_sent": self._batches_sent,
                "failed_batches": self._failed_batches,
                "duration_seconds": (self._end_time - self._start_time).total_seconds(),
                "start_time": self._sync_start_timestamp.isoformat(),
                "end_time": self._sync_end_timestamp.isoformat(),
            }

            _LOGGER.info(
                "Historical sync %s: %d entities, %d/%d points sent in %d batches (%.1fs)",
                self._status.value,
                self._processed_entities,
                self._sent_data_points,
                self._total_data_points,
                self._batches_sent,
                result["duration_seconds"],
            )

            return result

        except Exception as err:
            _LOGGER.exception("Historical sync failed: %s", err)
            self._status = SyncStatus.FAILED
            self._end_time = dt_util.utcnow()

            return {
                "status": "failed",
                "error": str(err),
                "processed_entities": self._processed_entities,
                "sent_data_points": self._sent_data_points,
            }

    async def _async_sync_entity_history(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Sync historical data for a single entity.

        Args:
            entity_id: Entity ID to sync.
            start_time: Start of time range.
            end_time: End of time range.
        """
        # Get input_id for entity
        input_id = self.signal_manager.get_input_id_for_entity(entity_id)
        if not input_id:
            _LOGGER.warning("No input_id found for entity %s, skipping", entity_id)
            return

        # Query history from recorder
        _LOGGER.debug(
            "Querying history for %s from %s to %s",
            entity_id,
            start_time.isoformat(),
            end_time.isoformat(),
        )

        try:
            # Use recorder.history.get_significant_states to get state changes
            # Run in executor since this is a blocking database query
            states = await self.hass.async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start_time,
                end_time,
                [entity_id],
                None,  # filters
                True,  # include_start_time_state
                True,  # significant_changes_only
                False,  # minimal_response
            )

            entity_states = states.get(entity_id, [])

            if not entity_states:
                _LOGGER.debug("No historical data found for %s", entity_id)
                return

            _LOGGER.info(
                "Found %d historical states for %s",
                len(entity_states),
                entity_id,
            )

            # Extract numeric values and prepare DataFrame
            data_points = []

            for state in entity_states:
                # Try to extract numeric value
                try:
                    # Skip unavailable/unknown states
                    if state.state in ("unavailable", "unknown", None):
                        continue

                    # Try direct conversion
                    value = float(state.state)

                    data_points.append((state.last_updated, value))

                except (ValueError, TypeError):
                    # Try boolean conversion
                    if state.state in ("on", "true", "yes"):
                        data_points.append((state.last_updated, 1.0))
                    elif state.state in ("off", "false", "no"):
                        data_points.append((state.last_updated, 0.0))
                    # Skip non-numeric states
                    continue

            if not data_points:
                _LOGGER.debug("No numeric data points found for %s", entity_id)
                return

            self._total_data_points += len(data_points)

            # Send data in batches
            await self._async_send_data_in_batches(input_id, data_points)

        except Exception as err:
            _LOGGER.error(
                "Failed to sync history for %s: %s",
                entity_id,
                err,
            )

    async def _async_send_data_in_batches(
        self,
        input_id: str,
        data_points: list[tuple[datetime, float]],
    ) -> None:
        """Send data points in batches.

        Args:
            input_id: Signal input ID.
            data_points: List of (timestamp, value) tuples.
        """
        total_points = len(data_points)
        sent = 0

        # Sort by timestamp
        data_points.sort(key=lambda x: x[0])

        # Send in batches
        for i in range(0, total_points, self.batch_size):
            if self._cancel_requested:
                break

            batch = data_points[i : i + self.batch_size]

            # Build DataFrame
            times = [point[0].isoformat() for point in batch]
            values = [point[1] for point in batch]

            dataframe = DataFrame(
                times=times,
                series={input_id: values},
            )

            # Send batch
            try:
                await self.client.async_insert_dataframe(dataframe)

                sent += len(batch)
                self._sent_data_points += len(batch)
                self._batches_sent += 1

                _LOGGER.debug(
                    "Sent historical batch for %s: %d/%d points",
                    input_id,
                    sent,
                    total_points,
                )

                # Delay between batches to avoid overwhelming API
                if i + self.batch_size < total_points:
                    await asyncio.sleep(self.batch_interval_seconds)

            except Exception as err:
                self._failed_batches += 1
                _LOGGER.error(
                    "Failed to send historical batch for %s: %s",
                    input_id,
                    err,
                )

                # Continue with next batch
                continue

    def cancel_sync(self) -> None:
        """Cancel ongoing sync operation."""
        if self._status == SyncStatus.IN_PROGRESS:
            _LOGGER.warning("Cancelling historical data sync")
            self._cancel_requested = True

    def get_sync_status(self) -> dict[str, Any]:
        """Get current sync status.

        Returns:
            Dictionary with sync status and progress.
        """
        progress = 0.0
        if self._total_entities > 0:
            progress = (self._processed_entities / self._total_entities) * 100

        duration = None
        if self._start_time:
            end = self._end_time or dt_util.utcnow()
            duration = (end - self._start_time).total_seconds()

        return {
            "status": self._status.value,
            "progress_percent": round(progress, 1),
            "total_entities": self._total_entities,
            "processed_entities": self._processed_entities,
            "current_entity": self._current_entity,
            "total_data_points": self._total_data_points,
            "sent_data_points": self._sent_data_points,
            "batches_sent": self._batches_sent,
            "failed_batches": self._failed_batches,
            "duration_seconds": round(duration, 1) if duration else None,
            "start_time": (
                self._sync_start_timestamp.isoformat()
                if self._sync_start_timestamp
                else None
            ),
            "end_time": (
                self._sync_end_timestamp.isoformat()
                if self._sync_end_timestamp
                else None
            ),
        }


def estimate_data_points(
    hass: HomeAssistant,
    entity_ids: list[str],
    start_time: datetime,
    end_time: datetime,
) -> int:
    """Estimate number of data points for historical sync.

    Args:
        hass: Home Assistant instance.
        entity_ids: List of entity IDs.
        start_time: Start of time range.
        end_time: End of time range.

    Returns:
        Estimated number of data points.
    """
    duration_hours = (end_time - start_time).total_seconds() / 3600

    # Estimate based on typical update frequencies
    # Sensors: ~1 update per minute
    # Binary sensors: ~0.1 updates per minute
    # Other: ~0.5 updates per minute

    total_estimate = 0

    for entity_id in entity_ids:
        domain = entity_id.split(".")[0]

        if domain == "sensor":
            # ~60 updates per hour
            total_estimate += int(duration_hours * 60)
        elif domain == "binary_sensor":
            # ~6 updates per hour
            total_estimate += int(duration_hours * 6)
        else:
            # ~30 updates per hour
            total_estimate += int(duration_hours * 30)

    return total_estimate


def estimate_sync_duration(
    data_points: int,
    batch_size: int = 500,
    batch_interval_seconds: float = 5.0,
    api_call_seconds: float = 2.0,
) -> float:
    """Estimate duration of historical sync.

    Args:
        data_points: Number of data points to sync.
        batch_size: Batch size.
        batch_interval_seconds: Delay between batches.
        api_call_seconds: Average API call duration.

    Returns:
        Estimated duration in seconds.
    """
    batches = (data_points + batch_size - 1) // batch_size

    # Time = (batches * (API call + delay))
    duration = batches * (api_call_seconds + batch_interval_seconds)

    return duration
