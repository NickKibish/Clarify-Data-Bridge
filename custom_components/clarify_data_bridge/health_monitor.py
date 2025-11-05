"""Integration health monitoring and diagnostics."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from statistics import mean, median
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Overall health status."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class APICallMetrics:
    """Metrics for a single API call."""

    timestamp: datetime
    duration_ms: float
    success: bool
    endpoint: str
    error_message: str = ""


@dataclass
class HealthMetrics:
    """Comprehensive health metrics."""

    # API metrics
    api_calls_total: int = 0
    api_calls_successful: int = 0
    api_calls_failed: int = 0
    api_response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    api_errors: deque = field(default_factory=lambda: deque(maxlen=50))

    # Transmission metrics
    transmissions_total: int = 0
    transmissions_successful: int = 0
    transmissions_failed: int = 0
    data_points_sent: int = 0

    # Buffer metrics
    buffer_overflows: int = 0
    max_buffer_size_reached: int = 0
    average_buffer_utilization: float = 0.0

    # Error tracking
    consecutive_failures: int = 0
    error_frequencies: dict[str, int] = field(default_factory=dict)

    # Timing
    last_successful_transmission: datetime | None = None
    last_failed_transmission: datetime | None = None
    uptime_start: datetime = field(default_factory=dt_util.utcnow)


class IntegrationHealthMonitor:
    """Monitor integration health and provide diagnostics."""

    def __init__(self, history_size: int = 100) -> None:
        """Initialize health monitor.

        Args:
            history_size: Number of historical metrics to keep.
        """
        self.history_size = history_size
        self.metrics = HealthMetrics()

        # Recent API call history
        self._api_call_history: deque[APICallMetrics] = deque(maxlen=history_size)

        # Performance tracking
        self._buffer_utilization_history: deque[float] = deque(maxlen=100)

        _LOGGER.debug("Initialized IntegrationHealthMonitor")

    def record_api_call(
        self,
        duration_ms: float,
        success: bool,
        endpoint: str = "unknown",
        error_message: str = "",
    ) -> None:
        """Record an API call for monitoring.

        Args:
            duration_ms: Duration in milliseconds.
            success: Whether call was successful.
            endpoint: API endpoint called.
            error_message: Error message if failed.
        """
        now = dt_util.utcnow()

        # Create metrics entry
        call_metrics = APICallMetrics(
            timestamp=now,
            duration_ms=duration_ms,
            success=success,
            endpoint=endpoint,
            error_message=error_message,
        )

        self._api_call_history.append(call_metrics)

        # Update counters
        self.metrics.api_calls_total += 1

        if success:
            self.metrics.api_calls_successful += 1
            self.metrics.consecutive_failures = 0
            self.metrics.api_response_times.append(duration_ms)
        else:
            self.metrics.api_calls_failed += 1
            self.metrics.consecutive_failures += 1

            # Track error
            error_type = self._classify_error(error_message)
            self.metrics.error_frequencies[error_type] = (
                self.metrics.error_frequencies.get(error_type, 0) + 1
            )

            self.metrics.api_errors.append((now, error_message))

        _LOGGER.debug(
            "Recorded API call: %s, duration=%.1fms, success=%s",
            endpoint,
            duration_ms,
            success,
        )

    def record_transmission(
        self,
        success: bool,
        data_points: int = 0,
    ) -> None:
        """Record a data transmission attempt.

        Args:
            success: Whether transmission was successful.
            data_points: Number of data points transmitted.
        """
        now = dt_util.utcnow()

        self.metrics.transmissions_total += 1

        if success:
            self.metrics.transmissions_successful += 1
            self.metrics.data_points_sent += data_points
            self.metrics.last_successful_transmission = now
        else:
            self.metrics.transmissions_failed += 1
            self.metrics.last_failed_transmission = now

    def record_buffer_utilization(
        self,
        current_size: int,
        max_size: int,
    ) -> None:
        """Record buffer utilization.

        Args:
            current_size: Current buffer size.
            max_size: Maximum buffer size.
        """
        if max_size > 0:
            utilization = (current_size / max_size) * 100
            self._buffer_utilization_history.append(utilization)

            # Update average
            if self._buffer_utilization_history:
                self.metrics.average_buffer_utilization = mean(
                    self._buffer_utilization_history
                )

            # Track events
            if current_size >= max_size:
                self.metrics.buffer_overflows += 1

            if current_size >= max_size * 0.9:
                self.metrics.max_buffer_size_reached += 1

    def _classify_error(self, error_message: str) -> str:
        """Classify error message.

        Args:
            error_message: Error message to classify.

        Returns:
            Error classification.
        """
        error_lower = error_message.lower()

        if "network" in error_lower or "connection" in error_lower:
            return "network_error"
        elif "timeout" in error_lower:
            return "timeout_error"
        elif "401" in error_lower or "403" in error_lower or "auth" in error_lower:
            return "authentication_error"
        elif "429" in error_lower or "rate limit" in error_lower:
            return "rate_limit_error"
        elif "500" in error_lower or "502" in error_lower or "503" in error_lower:
            return "server_error"
        else:
            return "unknown_error"

    def get_health_status(self) -> HealthStatus:
        """Calculate overall health status.

        Returns:
            HealthStatus enum value.
        """
        score = 100  # Start with perfect score

        # API success rate (30% weight)
        if self.metrics.api_calls_total > 0:
            api_success_rate = (
                self.metrics.api_calls_successful / self.metrics.api_calls_total
            ) * 100

            if api_success_rate < 50:
                score -= 30
            elif api_success_rate < 80:
                score -= 20
            elif api_success_rate < 95:
                score -= 10

        # Transmission success rate (30% weight)
        if self.metrics.transmissions_total > 0:
            transmission_success_rate = (
                self.metrics.transmissions_successful / self.metrics.transmissions_total
            ) * 100

            if transmission_success_rate < 50:
                score -= 30
            elif transmission_success_rate < 80:
                score -= 20
            elif transmission_success_rate < 95:
                score -= 10

        # Consecutive failures (20% weight)
        if self.metrics.consecutive_failures >= 10:
            score -= 20
        elif self.metrics.consecutive_failures >= 5:
            score -= 15
        elif self.metrics.consecutive_failures >= 3:
            score -= 10

        # Buffer issues (10% weight)
        if self.metrics.buffer_overflows > 10:
            score -= 10
        elif self.metrics.buffer_overflows > 5:
            score -= 5

        # Recent activity (10% weight)
        if self.metrics.last_successful_transmission:
            time_since_success = (
                dt_util.utcnow() - self.metrics.last_successful_transmission
            ).total_seconds()

            if time_since_success > 1800:  # 30 minutes
                score -= 10
            elif time_since_success > 600:  # 10 minutes
                score -= 5

        # Determine status
        if score >= 90:
            return HealthStatus.EXCELLENT
        elif score >= 75:
            return HealthStatus.GOOD
        elif score >= 50:
            return HealthStatus.FAIR
        elif score >= 25:
            return HealthStatus.POOR
        else:
            return HealthStatus.CRITICAL

    def get_api_performance_metrics(self) -> dict[str, Any]:
        """Get API performance metrics.

        Returns:
            Dictionary with API performance information.
        """
        if not self.metrics.api_response_times:
            return {
                "calls_total": self.metrics.api_calls_total,
                "calls_successful": self.metrics.api_calls_successful,
                "calls_failed": self.metrics.api_calls_failed,
                "success_rate": 0.0,
            }

        response_times = list(self.metrics.api_response_times)

        return {
            "calls_total": self.metrics.api_calls_total,
            "calls_successful": self.metrics.api_calls_successful,
            "calls_failed": self.metrics.api_calls_failed,
            "success_rate": round(
                (self.metrics.api_calls_successful / self.metrics.api_calls_total) * 100,
                2,
            )
            if self.metrics.api_calls_total > 0
            else 0.0,
            "avg_response_time_ms": round(mean(response_times), 1),
            "median_response_time_ms": round(median(response_times), 1),
            "min_response_time_ms": round(min(response_times), 1),
            "max_response_time_ms": round(max(response_times), 1),
        }

    def get_transmission_metrics(self) -> dict[str, Any]:
        """Get transmission metrics.

        Returns:
            Dictionary with transmission information.
        """
        return {
            "total": self.metrics.transmissions_total,
            "successful": self.metrics.transmissions_successful,
            "failed": self.metrics.transmissions_failed,
            "success_rate": round(
                (self.metrics.transmissions_successful / self.metrics.transmissions_total)
                * 100,
                2,
            )
            if self.metrics.transmissions_total > 0
            else 0.0,
            "data_points_sent": self.metrics.data_points_sent,
            "last_successful": (
                self.metrics.last_successful_transmission.isoformat()
                if self.metrics.last_successful_transmission
                else None
            ),
            "last_failed": (
                self.metrics.last_failed_transmission.isoformat()
                if self.metrics.last_failed_transmission
                else None
            ),
        }

    def get_buffer_metrics(self) -> dict[str, Any]:
        """Get buffer metrics.

        Returns:
            Dictionary with buffer information.
        """
        return {
            "average_utilization_percent": round(
                self.metrics.average_buffer_utilization, 2
            ),
            "overflows": self.metrics.buffer_overflows,
            "max_size_reached_count": self.metrics.max_buffer_size_reached,
        }

    def get_error_summary(self) -> dict[str, Any]:
        """Get error summary.

        Returns:
            Dictionary with error information.
        """
        total_errors = sum(self.metrics.error_frequencies.values())

        recent_errors = []
        for timestamp, message in list(self.metrics.api_errors)[-10:]:
            recent_errors.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "message": message[:200],
                }
            )

        return {
            "consecutive_failures": self.metrics.consecutive_failures,
            "total_errors": total_errors,
            "error_types": dict(self.metrics.error_frequencies),
            "recent_errors": recent_errors,
        }

    def get_uptime_metrics(self) -> dict[str, Any]:
        """Get uptime metrics.

        Returns:
            Dictionary with uptime information.
        """
        uptime = dt_util.utcnow() - self.metrics.uptime_start
        uptime_seconds = uptime.total_seconds()

        return {
            "uptime_seconds": round(uptime_seconds, 1),
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "uptime_days": round(uptime_seconds / 86400, 2),
            "start_time": self.metrics.uptime_start.isoformat(),
        }

    def get_comprehensive_report(self) -> dict[str, Any]:
        """Get comprehensive health report.

        Returns:
            Dictionary with all health information.
        """
        health_status = self.get_health_status()

        return {
            "health_status": health_status.value,
            "api_performance": self.get_api_performance_metrics(),
            "transmission": self.get_transmission_metrics(),
            "buffer": self.get_buffer_metrics(),
            "errors": self.get_error_summary(),
            "uptime": self.get_uptime_metrics(),
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> list[str]:
        """Generate health recommendations.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # API success rate
        if self.metrics.api_calls_total > 10:
            api_success_rate = (
                self.metrics.api_calls_successful / self.metrics.api_calls_total
            ) * 100

            if api_success_rate < 80:
                recommendations.append(
                    f"Low API success rate ({api_success_rate:.1f}%). Check network connectivity and API credentials."
                )

        # Consecutive failures
        if self.metrics.consecutive_failures >= 5:
            recommendations.append(
                f"{self.metrics.consecutive_failures} consecutive failures detected. Check error logs and Clarify.io status."
            )

        # Buffer overflows
        if self.metrics.buffer_overflows > 5:
            recommendations.append(
                f"{self.metrics.buffer_overflows} buffer overflows detected. Consider increasing buffer size or transmission frequency."
            )

        # Response time
        if self.metrics.api_response_times:
            avg_response = mean(self.metrics.api_response_times)
            if avg_response > 5000:  # 5 seconds
                recommendations.append(
                    f"High average API response time ({avg_response:.0f}ms). Check network latency or Clarify.io service status."
                )

        # Recent activity
        if self.metrics.last_successful_transmission:
            time_since_success = (
                dt_util.utcnow() - self.metrics.last_successful_transmission
            ).total_seconds()

            if time_since_success > 1800:  # 30 minutes
                recommendations.append(
                    f"No successful transmission in {int(time_since_success/60)} minutes. Check integration status."
                )

        # Error patterns
        if "rate_limit_error" in self.metrics.error_frequencies:
            recommendations.append(
                "Rate limit errors detected. Consider increasing batch_interval or reducing entity count."
            )

        if "authentication_error" in self.metrics.error_frequencies:
            recommendations.append(
                "Authentication errors detected. Verify OAuth 2.0 credentials in configuration."
            )

        if not recommendations:
            recommendations.append("Integration is operating normally.")

        return recommendations

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self.metrics = HealthMetrics()
        self._api_call_history.clear()
        self._buffer_utilization_history.clear()

        _LOGGER.info("Reset health monitor metrics")
