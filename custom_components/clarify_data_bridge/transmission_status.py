"""Transmission status tracking for Clarify Data Bridge."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class TransmissionStatus(Enum):
    """Status of transmission."""

    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    ABANDONED = "abandoned"


@dataclass
class TransmissionEntry:
    """Single transmission record."""

    timestamp: datetime
    status: TransmissionStatus
    data_points: int
    series_count: int
    duration_ms: float = 0.0
    error_message: str = ""
    retry_count: int = 0
    buffer_trigger: str = ""


class TransmissionStatusTracker:
    """Track transmission status and provide visibility.

    Maintains history of recent transmissions for diagnostics
    and user visibility.
    """

    def __init__(
        self,
        max_history: int = 100,
    ) -> None:
        """Initialize transmission status tracker.

        Args:
            max_history: Maximum number of transmission records to keep.
        """
        self.max_history = max_history

        # Recent transmission history
        self._history: deque[TransmissionEntry] = deque(maxlen=max_history)

        # Running statistics
        self._total_transmissions = 0
        self._successful_transmissions = 0
        self._failed_transmissions = 0
        self._total_data_points = 0
        self._total_duration_ms = 0.0

        # Current status
        self._last_transmission_time: datetime | None = None
        self._last_success_time: datetime | None = None
        self._last_failure_time: datetime | None = None
        self._current_status: TransmissionStatus = TransmissionStatus.SUCCESS

        # Error tracking
        self._consecutive_failures = 0
        self._recent_errors: deque[tuple[datetime, str]] = deque(maxlen=10)

        _LOGGER.debug("Initialized TransmissionStatusTracker with max_history=%d", max_history)

    def record_transmission(
        self,
        status: TransmissionStatus,
        data_points: int,
        series_count: int,
        duration_ms: float = 0.0,
        error_message: str = "",
        retry_count: int = 0,
        buffer_trigger: str = "",
    ) -> None:
        """Record a transmission attempt.

        Args:
            status: Status of the transmission.
            data_points: Number of data points transmitted.
            series_count: Number of series (signals) in transmission.
            duration_ms: Duration in milliseconds.
            error_message: Error message if failed.
            retry_count: Number of retry attempts.
            buffer_trigger: What triggered the buffer flush.
        """
        now = dt_util.utcnow()

        entry = TransmissionEntry(
            timestamp=now,
            status=status,
            data_points=data_points,
            series_count=series_count,
            duration_ms=duration_ms,
            error_message=error_message,
            retry_count=retry_count,
            buffer_trigger=buffer_trigger,
        )

        self._history.append(entry)

        # Update statistics
        self._total_transmissions += 1
        self._last_transmission_time = now
        self._current_status = status

        if status == TransmissionStatus.SUCCESS:
            self._successful_transmissions += 1
            self._last_success_time = now
            self._consecutive_failures = 0
            self._total_data_points += data_points
            self._total_duration_ms += duration_ms

            _LOGGER.info(
                "Transmission successful: %d points, %d series, %.1fms, trigger=%s",
                data_points,
                series_count,
                duration_ms,
                buffer_trigger,
            )

        elif status in (TransmissionStatus.FAILED, TransmissionStatus.ABANDONED):
            self._failed_transmissions += 1
            self._last_failure_time = now
            self._consecutive_failures += 1

            # Track recent errors
            self._recent_errors.append((now, error_message))

            _LOGGER.error(
                "Transmission %s: %d points, error=%s, consecutive_failures=%d",
                status.value,
                data_points,
                error_message[:100],
                self._consecutive_failures,
            )

        elif status == TransmissionStatus.RETRYING:
            _LOGGER.warning(
                "Transmission retrying: %d points, retry_count=%d, error=%s",
                data_points,
                retry_count,
                error_message[:100],
            )

    def get_current_status(self) -> dict[str, Any]:
        """Get current transmission status.

        Returns:
            Dictionary with current status information.
        """
        now = dt_util.utcnow()

        # Calculate uptime metrics
        success_rate = 0.0
        if self._total_transmissions > 0:
            success_rate = (
                self._successful_transmissions / self._total_transmissions * 100
            )

        avg_duration_ms = 0.0
        if self._successful_transmissions > 0:
            avg_duration_ms = self._total_duration_ms / self._successful_transmissions

        # Time since last transmission
        time_since_last = None
        if self._last_transmission_time:
            time_since_last = (now - self._last_transmission_time).total_seconds()

        # Time since last success
        time_since_success = None
        if self._last_success_time:
            time_since_success = (now - self._last_success_time).total_seconds()

        return {
            "status": self._current_status.value,
            "last_transmission_time": (
                self._last_transmission_time.isoformat()
                if self._last_transmission_time
                else None
            ),
            "last_success_time": (
                self._last_success_time.isoformat()
                if self._last_success_time
                else None
            ),
            "last_failure_time": (
                self._last_failure_time.isoformat()
                if self._last_failure_time
                else None
            ),
            "time_since_last_transmission_seconds": time_since_last,
            "time_since_last_success_seconds": time_since_success,
            "consecutive_failures": self._consecutive_failures,
            "health_status": self._get_health_status(),
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get transmission statistics.

        Returns:
            Dictionary of statistics.
        """
        success_rate = 0.0
        if self._total_transmissions > 0:
            success_rate = (
                self._successful_transmissions / self._total_transmissions * 100
            )

        avg_duration_ms = 0.0
        if self._successful_transmissions > 0:
            avg_duration_ms = self._total_duration_ms / self._successful_transmissions

        avg_data_points = 0.0
        if self._successful_transmissions > 0:
            avg_data_points = self._total_data_points / self._successful_transmissions

        return {
            "total_transmissions": self._total_transmissions,
            "successful_transmissions": self._successful_transmissions,
            "failed_transmissions": self._failed_transmissions,
            "success_rate": round(success_rate, 2),
            "total_data_points_sent": self._total_data_points,
            "average_data_points_per_transmission": round(avg_data_points, 1),
            "average_transmission_duration_ms": round(avg_duration_ms, 1),
        }

    def get_recent_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent transmission history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent transmission records.
        """
        history = list(self._history)[-limit:]

        return [
            {
                "timestamp": entry.timestamp.isoformat(),
                "status": entry.status.value,
                "data_points": entry.data_points,
                "series_count": entry.series_count,
                "duration_ms": round(entry.duration_ms, 1),
                "error_message": entry.error_message[:100] if entry.error_message else "",
                "retry_count": entry.retry_count,
                "buffer_trigger": entry.buffer_trigger,
            }
            for entry in history
        ]

    def get_recent_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent error messages.

        Args:
            limit: Maximum number of errors to return.

        Returns:
            List of recent errors with timestamps.
        """
        errors = list(self._recent_errors)[-limit:]

        return [
            {
                "timestamp": timestamp.isoformat(),
                "error_message": error_message[:200],
            }
            for timestamp, error_message in errors
        ]

    def _get_health_status(self) -> str:
        """Determine overall health status.

        Returns:
            Health status: "healthy", "degraded", "unhealthy".
        """
        # No transmissions yet
        if self._total_transmissions == 0:
            return "unknown"

        # Recent consecutive failures
        if self._consecutive_failures >= 5:
            return "unhealthy"
        elif self._consecutive_failures >= 3:
            return "degraded"

        # Success rate check
        if self._total_transmissions >= 10:
            success_rate = (
                self._successful_transmissions / self._total_transmissions * 100
            )

            if success_rate < 50:
                return "unhealthy"
            elif success_rate < 80:
                return "degraded"

        # Check time since last success
        if self._last_success_time:
            time_since_success = (
                dt_util.utcnow() - self._last_success_time
            ).total_seconds()

            # No successful transmission in 30 minutes
            if time_since_success > 1800:
                return "unhealthy"
            # No successful transmission in 10 minutes
            elif time_since_success > 600:
                return "degraded"

        return "healthy"

    def get_health_summary(self) -> dict[str, Any]:
        """Get comprehensive health summary.

        Returns:
            Dictionary with health information.
        """
        health_status = self._get_health_status()

        recommendations = []
        if self._consecutive_failures >= 3:
            recommendations.append("Multiple consecutive failures detected. Check network connectivity and API credentials.")

        if self._last_success_time:
            time_since_success = (
                dt_util.utcnow() - self._last_success_time
            ).total_seconds()
            if time_since_success > 600:
                recommendations.append(f"No successful transmission in {int(time_since_success/60)} minutes. Review error logs.")

        if self._total_transmissions >= 10:
            success_rate = (
                self._successful_transmissions / self._total_transmissions * 100
            )
            if success_rate < 80:
                recommendations.append(f"Low success rate ({success_rate:.1f}%). Check API configuration and network stability.")

        return {
            "health_status": health_status,
            "consecutive_failures": self._consecutive_failures,
            "recent_errors_count": len(self._recent_errors),
            "recommendations": recommendations,
            "last_error": (
                self._recent_errors[-1][1][:200]
                if self._recent_errors
                else None
            ),
        }

    def reset_statistics(self) -> None:
        """Reset all statistics."""
        self._total_transmissions = 0
        self._successful_transmissions = 0
        self._failed_transmissions = 0
        self._total_data_points = 0
        self._total_duration_ms = 0.0
        self._consecutive_failures = 0

        _LOGGER.info("Reset transmission statistics")

    def clear_history(self) -> None:
        """Clear transmission history."""
        self._history.clear()
        self._recent_errors.clear()

        _LOGGER.info("Cleared transmission history")
