"""Performance tuning and resource management for Clarify Data Bridge."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import psutil
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class PerformanceProfile:
    """Performance tuning profile."""

    name: str
    description: str
    batch_interval: int
    max_batch_size: int
    buffer_strategy: str
    max_retry_queue_size: int
    max_concurrent_requests: int
    memory_limit_mb: int
    enable_aggregation: bool
    aggregation_window: int


# Pre-defined performance profiles
MINIMAL_PROFILE = PerformanceProfile(
    name="Minimal Resource Usage",
    description="Lowest memory and CPU usage, higher latency",
    batch_interval=600,  # 10 minutes
    max_batch_size=50,
    buffer_strategy="time",
    max_retry_queue_size=100,
    max_concurrent_requests=1,
    memory_limit_mb=50,
    enable_aggregation=True,
    aggregation_window=600,
)

BALANCED_PROFILE = PerformanceProfile(
    name="Balanced",
    description="Balance between performance and resource usage",
    batch_interval=300,  # 5 minutes
    max_batch_size=100,
    buffer_strategy="hybrid",
    max_retry_queue_size=500,
    max_concurrent_requests=2,
    memory_limit_mb=100,
    enable_aggregation=False,
    aggregation_window=300,
)

HIGH_PERFORMANCE_PROFILE = PerformanceProfile(
    name="High Performance",
    description="Lower latency, higher resource usage",
    batch_interval=60,  # 1 minute
    max_batch_size=200,
    buffer_strategy="priority",
    max_retry_queue_size=1000,
    max_concurrent_requests=4,
    memory_limit_mb=200,
    enable_aggregation=False,
    aggregation_window=60,
)

REAL_TIME_PROFILE = PerformanceProfile(
    name="Real-Time",
    description="Minimal latency, highest resource usage",
    batch_interval=30,  # 30 seconds
    max_batch_size=500,
    buffer_strategy="priority",
    max_retry_queue_size=2000,
    max_concurrent_requests=8,
    memory_limit_mb=500,
    enable_aggregation=False,
    aggregation_window=30,
)

AVAILABLE_PROFILES = {
    "minimal": MINIMAL_PROFILE,
    "balanced": BALANCED_PROFILE,
    "high_performance": HIGH_PERFORMANCE_PROFILE,
    "real_time": REAL_TIME_PROFILE,
}


class PerformanceManager:
    """Manages performance tuning and resource monitoring."""

    def __init__(
        self,
        profile_name: str = "balanced",
        custom_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize performance manager.

        Args:
            profile_name: Name of performance profile to use.
            custom_config: Custom configuration overrides.
        """
        # Load profile
        if profile_name not in AVAILABLE_PROFILES:
            _LOGGER.warning(
                "Unknown profile '%s', using 'balanced'",
                profile_name,
            )
            profile_name = "balanced"

        self.profile = AVAILABLE_PROFILES[profile_name]
        self.profile_name = profile_name

        # Apply custom overrides
        if custom_config:
            self._apply_custom_config(custom_config)

        # Resource monitoring
        self._process = psutil.Process()
        self._initial_memory = self._get_memory_usage_mb()

        _LOGGER.info(
            "Initialized PerformanceManager with profile: %s",
            self.profile.name,
        )

    def _apply_custom_config(self, config: dict[str, Any]) -> None:
        """Apply custom configuration overrides.

        Args:
            config: Dictionary of configuration overrides.
        """
        for key, value in config.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
                _LOGGER.debug("Applied custom config: %s=%s", key, value)

    def get_batch_interval(self) -> int:
        """Get configured batch interval."""
        return self.profile.batch_interval

    def get_max_batch_size(self) -> int:
        """Get configured maximum batch size."""
        return self.profile.max_batch_size

    def get_buffer_strategy(self) -> str:
        """Get configured buffer strategy."""
        return self.profile.buffer_strategy

    def get_max_retry_queue_size(self) -> int:
        """Get configured maximum retry queue size."""
        return self.profile.max_retry_queue_size

    def get_max_concurrent_requests(self) -> int:
        """Get configured maximum concurrent API requests."""
        return self.profile.max_concurrent_requests

    def get_memory_limit_mb(self) -> int:
        """Get configured memory limit in MB."""
        return self.profile.memory_limit_mb

    def should_enable_aggregation(self) -> bool:
        """Check if data aggregation should be enabled."""
        return self.profile.enable_aggregation

    def get_aggregation_window(self) -> int:
        """Get aggregation window in seconds."""
        return self.profile.aggregation_window

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB.

        Returns:
            Memory usage in megabytes.
        """
        try:
            memory_info = self._process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception as err:
            _LOGGER.warning("Failed to get memory usage: %s", err)
            return 0.0

    def _get_cpu_percent(self) -> float:
        """Get current CPU usage percentage.

        Returns:
            CPU usage percentage.
        """
        try:
            return self._process.cpu_percent(interval=0.1)
        except Exception as err:
            _LOGGER.warning("Failed to get CPU usage: %s", err)
            return 0.0

    def get_resource_usage(self) -> dict[str, Any]:
        """Get current resource usage statistics.

        Returns:
            Dictionary with resource usage information.
        """
        current_memory = self._get_memory_usage_mb()
        memory_delta = current_memory - self._initial_memory

        return {
            "memory_usage_mb": round(current_memory, 2),
            "memory_delta_mb": round(memory_delta, 2),
            "memory_limit_mb": self.profile.memory_limit_mb,
            "memory_usage_percent": round(
                (current_memory / self.profile.memory_limit_mb) * 100, 2
            )
            if self.profile.memory_limit_mb > 0
            else 0.0,
            "cpu_percent": round(self._get_cpu_percent(), 2),
            "is_memory_exceeded": current_memory > self.profile.memory_limit_mb,
        }

    def check_memory_limit(self) -> tuple[bool, str]:
        """Check if memory usage is within limits.

        Returns:
            Tuple of (is_within_limit, message).
        """
        current_memory = self._get_memory_usage_mb()

        if current_memory > self.profile.memory_limit_mb:
            message = (
                f"Memory usage ({current_memory:.1f}MB) exceeds limit "
                f"({self.profile.memory_limit_mb}MB)"
            )
            _LOGGER.warning(message)
            return False, message

        return True, "Memory usage within limits"

    def suggest_optimization(
        self,
        buffer_size: int,
        retry_queue_size: int,
        transmission_rate: float,
    ) -> list[str]:
        """Suggest performance optimizations based on current metrics.

        Args:
            buffer_size: Current buffer size.
            retry_queue_size: Current retry queue size.
            transmission_rate: Current transmission rate (transmissions/minute).

        Returns:
            List of optimization suggestions.
        """
        suggestions = []

        # Check buffer utilization
        buffer_utilization = (buffer_size / self.profile.max_batch_size) * 100
        if buffer_utilization > 80:
            suggestions.append(
                f"Buffer utilization high ({buffer_utilization:.1f}%). "
                "Consider increasing max_batch_size or decreasing batch_interval."
            )

        # Check retry queue
        if retry_queue_size > self.profile.max_retry_queue_size * 0.8:
            suggestions.append(
                f"Retry queue near capacity ({retry_queue_size}/{self.profile.max_retry_queue_size}). "
                "Check network connectivity or increase retry queue size."
            )

        # Check transmission rate
        expected_rate = 60 / self.profile.batch_interval  # transmissions per minute
        if transmission_rate < expected_rate * 0.5:
            suggestions.append(
                f"Low transmission rate ({transmission_rate:.1f}/min, expected ~{expected_rate:.1f}/min). "
                "Check for errors or network issues."
            )

        # Check memory
        memory_usage = self._get_memory_usage_mb()
        if memory_usage > self.profile.memory_limit_mb * 0.9:
            suggestions.append(
                f"Memory usage high ({memory_usage:.1f}MB / {self.profile.memory_limit_mb}MB). "
                "Consider reducing buffer sizes or switching to 'minimal' profile."
            )

        # CPU check
        cpu_percent = self._get_cpu_percent()
        if cpu_percent > 50:
            suggestions.append(
                f"High CPU usage ({cpu_percent:.1f}%). "
                "Consider increasing batch_interval or reducing entity count."
            )

        return suggestions

    def get_profile_comparison(self) -> dict[str, dict[str, Any]]:
        """Get comparison of all available profiles.

        Returns:
            Dictionary mapping profile names to their configurations.
        """
        return {
            name: {
                "description": profile.description,
                "batch_interval": profile.batch_interval,
                "max_batch_size": profile.max_batch_size,
                "buffer_strategy": profile.buffer_strategy,
                "max_concurrent_requests": profile.max_concurrent_requests,
                "memory_limit_mb": profile.memory_limit_mb,
                "relative_latency": self._calculate_relative_latency(profile),
                "relative_resource_usage": self._calculate_relative_resource_usage(
                    profile
                ),
            }
            for name, profile in AVAILABLE_PROFILES.items()
        }

    def _calculate_relative_latency(self, profile: PerformanceProfile) -> str:
        """Calculate relative latency rating.

        Args:
            profile: Performance profile.

        Returns:
            Latency rating: "very_low", "low", "medium", "high".
        """
        if profile.batch_interval <= 30:
            return "very_low"
        elif profile.batch_interval <= 120:
            return "low"
        elif profile.batch_interval <= 300:
            return "medium"
        else:
            return "high"

    def _calculate_relative_resource_usage(self, profile: PerformanceProfile) -> str:
        """Calculate relative resource usage rating.

        Args:
            profile: Performance profile.

        Returns:
            Resource usage rating: "very_low", "low", "medium", "high", "very_high".
        """
        if profile.memory_limit_mb <= 50:
            return "very_low"
        elif profile.memory_limit_mb <= 100:
            return "low"
        elif profile.memory_limit_mb <= 200:
            return "medium"
        elif profile.memory_limit_mb <= 500:
            return "high"
        else:
            return "very_high"

    def export_config(self) -> dict[str, Any]:
        """Export current configuration.

        Returns:
            Dictionary representation of current configuration.
        """
        return {
            "profile_name": self.profile_name,
            "profile_description": self.profile.description,
            "batch_interval": self.profile.batch_interval,
            "max_batch_size": self.profile.max_batch_size,
            "buffer_strategy": self.profile.buffer_strategy,
            "max_retry_queue_size": self.profile.max_retry_queue_size,
            "max_concurrent_requests": self.profile.max_concurrent_requests,
            "memory_limit_mb": self.profile.memory_limit_mb,
            "enable_aggregation": self.profile.enable_aggregation,
            "aggregation_window": self.profile.aggregation_window,
        }
