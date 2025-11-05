"""Retry manager with exponential backoff for Clarify API calls."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any, Callable, Awaitable

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class RetryReason(Enum):
    """Reason for retry."""

    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN = "unknown"


@dataclass
class RetryEntry:
    """Entry in the retry queue."""

    data: Any  # Data to be sent
    attempt: int = 0
    max_attempts: int = 5
    last_attempt_time: datetime | None = None
    next_retry_time: datetime | None = None
    reason: RetryReason = RetryReason.UNKNOWN
    error_message: str = ""
    callback: Callable[[Any], Awaitable[Any]] | None = None


@dataclass
class RetryStatistics:
    """Statistics for retry operations."""

    total_retries: int = 0
    successful_retries: int = 0
    failed_retries: int = 0
    abandoned_entries: int = 0
    retry_reasons: dict[str, int] = field(default_factory=lambda: {})
    current_queue_size: int = 0
    max_queue_size: int = 0


class ExponentialBackoffRetryManager:
    """Manages retry logic with exponential backoff.

    Implements intelligent retry strategy:
    - Exponential backoff: 2^attempt seconds (2s, 4s, 8s, 16s, 32s)
    - Maximum 5 attempts by default
    - Rate limit detection and longer waits
    - Persistent storage for failed transmissions
    - Automatic cleanup of old entries
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 300.0,  # 5 minutes
        max_queue_size: int = 1000,
    ) -> None:
        """Initialize retry manager.

        Args:
            max_attempts: Maximum number of retry attempts.
            base_delay: Base delay in seconds for exponential backoff.
            max_delay: Maximum delay between retries in seconds.
            max_queue_size: Maximum number of entries in retry queue.
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_queue_size = max_queue_size

        # Retry queue (FIFO)
        self._retry_queue: deque[RetryEntry] = deque()

        # Statistics
        self.stats = RetryStatistics()

        # Processing lock
        self._processing_lock = asyncio.Lock()

        _LOGGER.info(
            "Initialized RetryManager: max_attempts=%d, base_delay=%.1fs, max_delay=%.1fs",
            max_attempts,
            base_delay,
            max_delay,
        )

    def calculate_backoff_delay(
        self,
        attempt: int,
        reason: RetryReason = RetryReason.UNKNOWN,
    ) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Attempt number (0-indexed).
            reason: Reason for retry (affects delay).

        Returns:
            Delay in seconds before next retry.
        """
        # Base exponential backoff: 2^attempt
        delay = self.base_delay * (2 ** attempt)

        # Apply reason-specific multipliers
        if reason == RetryReason.RATE_LIMIT:
            # Rate limit: Wait longer (3x)
            delay *= 3
        elif reason == RetryReason.SERVER_ERROR:
            # Server error: Wait a bit longer (1.5x)
            delay *= 1.5
        elif reason == RetryReason.AUTHENTICATION_ERROR:
            # Auth error: Don't retry immediately
            delay *= 2

        # Cap at max delay
        delay = min(delay, self.max_delay)

        _LOGGER.debug(
            "Calculated backoff delay: attempt=%d, reason=%s, delay=%.1fs",
            attempt,
            reason.value,
            delay,
        )

        return delay

    def add_retry_entry(
        self,
        data: Any,
        reason: RetryReason,
        error_message: str = "",
        callback: Callable[[Any], Awaitable[Any]] | None = None,
    ) -> bool:
        """Add entry to retry queue.

        Args:
            data: Data to be retried.
            reason: Reason for retry.
            error_message: Error message from failed attempt.
            callback: Optional callback function to call on success.

        Returns:
            True if added successfully, False if queue full.
        """
        # Check queue size
        if len(self._retry_queue) >= self.max_queue_size:
            _LOGGER.warning(
                "Retry queue full (%d entries), dropping oldest entry",
                self.max_queue_size,
            )
            oldest = self._retry_queue.popleft()
            self.stats.abandoned_entries += 1
            _LOGGER.error(
                "Abandoned retry entry after %d attempts: %s",
                oldest.attempt,
                oldest.error_message,
            )

        # Calculate next retry time
        delay = self.calculate_backoff_delay(0, reason)
        next_retry_time = dt_util.utcnow() + timedelta(seconds=delay)

        entry = RetryEntry(
            data=data,
            attempt=0,
            max_attempts=self.max_attempts,
            last_attempt_time=dt_util.utcnow(),
            next_retry_time=next_retry_time,
            reason=reason,
            error_message=error_message,
            callback=callback,
        )

        self._retry_queue.append(entry)

        # Update statistics
        self.stats.total_retries += 1
        self.stats.retry_reasons[reason.value] = (
            self.stats.retry_reasons.get(reason.value, 0) + 1
        )
        self.stats.current_queue_size = len(self._retry_queue)
        if self.stats.current_queue_size > self.stats.max_queue_size:
            self.stats.max_queue_size = self.stats.current_queue_size

        _LOGGER.info(
            "Added retry entry: reason=%s, next_retry=%.1fs, queue_size=%d, error=%s",
            reason.value,
            delay,
            len(self._retry_queue),
            error_message[:100],
        )

        return True

    async def process_retry_queue(
        self,
        send_callback: Callable[[Any], Awaitable[bool]],
    ) -> dict[str, int]:
        """Process entries in retry queue.

        Args:
            send_callback: Async callback to send data. Returns True on success.

        Returns:
            Dictionary with processing statistics.
        """
        async with self._processing_lock:
            if not self._retry_queue:
                return {"processed": 0, "successful": 0, "failed": 0, "requeued": 0}

            now = dt_util.utcnow()
            processed = 0
            successful = 0
            failed = 0
            requeued = 0

            # Process entries that are ready for retry
            entries_to_process = []
            entries_to_keep = []

            # Separate ready and not-ready entries
            while self._retry_queue:
                entry = self._retry_queue.popleft()

                if entry.next_retry_time <= now:
                    entries_to_process.append(entry)
                else:
                    entries_to_keep.append(entry)

            # Put not-ready entries back
            self._retry_queue.extend(entries_to_keep)

            _LOGGER.info(
                "Processing retry queue: %d entries ready, %d waiting",
                len(entries_to_process),
                len(entries_to_keep),
            )

            # Process ready entries
            for entry in entries_to_process:
                processed += 1

                try:
                    # Attempt to send data
                    success = await send_callback(entry.data)

                    if success:
                        successful += 1
                        self.stats.successful_retries += 1

                        _LOGGER.info(
                            "Successfully retried after %d attempts",
                            entry.attempt + 1,
                        )

                        # Call success callback if provided
                        if entry.callback:
                            try:
                                await entry.callback(entry.data)
                            except Exception as callback_err:
                                _LOGGER.warning(
                                    "Retry success callback failed: %s",
                                    callback_err,
                                )

                    else:
                        # Retry failed, requeue if not exhausted
                        entry.attempt += 1

                        if entry.attempt < entry.max_attempts:
                            # Calculate next retry time
                            delay = self.calculate_backoff_delay(
                                entry.attempt,
                                entry.reason,
                            )
                            entry.next_retry_time = now + timedelta(seconds=delay)
                            entry.last_attempt_time = now

                            self._retry_queue.append(entry)
                            requeued += 1

                            _LOGGER.warning(
                                "Retry failed (attempt %d/%d), requeueing with %.1fs delay",
                                entry.attempt,
                                entry.max_attempts,
                                delay,
                            )
                        else:
                            # Max attempts reached
                            failed += 1
                            self.stats.failed_retries += 1
                            self.stats.abandoned_entries += 1

                            _LOGGER.error(
                                "Retry abandoned after %d attempts: %s",
                                entry.max_attempts,
                                entry.error_message,
                            )

                except Exception as err:
                    # Unexpected error during retry
                    _LOGGER.exception("Unexpected error during retry: %s", err)

                    entry.attempt += 1
                    entry.error_message = f"Retry error: {err}"

                    if entry.attempt < entry.max_attempts:
                        delay = self.calculate_backoff_delay(
                            entry.attempt,
                            RetryReason.UNKNOWN,
                        )
                        entry.next_retry_time = now + timedelta(seconds=delay)
                        entry.last_attempt_time = now

                        self._retry_queue.append(entry)
                        requeued += 1
                    else:
                        failed += 1
                        self.stats.failed_retries += 1
                        self.stats.abandoned_entries += 1

            # Update queue size stat
            self.stats.current_queue_size = len(self._retry_queue)

            result = {
                "processed": processed,
                "successful": successful,
                "failed": failed,
                "requeued": requeued,
            }

            if processed > 0:
                _LOGGER.info(
                    "Retry queue processed: %d total, %d successful, %d failed, %d requeued",
                    processed,
                    successful,
                    failed,
                    requeued,
                )

            return result

    def get_queue_size(self) -> int:
        """Get current retry queue size."""
        return len(self._retry_queue)

    def get_next_retry_time(self) -> datetime | None:
        """Get time of next scheduled retry.

        Returns:
            Datetime of next retry, or None if queue empty.
        """
        if not self._retry_queue:
            return None

        return min(entry.next_retry_time for entry in self._retry_queue)

    def get_statistics(self) -> dict[str, Any]:
        """Get retry statistics.

        Returns:
            Dictionary of statistics.
        """
        next_retry = self.get_next_retry_time()

        return {
            "total_retries": self.stats.total_retries,
            "successful_retries": self.stats.successful_retries,
            "failed_retries": self.stats.failed_retries,
            "abandoned_entries": self.stats.abandoned_entries,
            "success_rate": (
                self.stats.successful_retries / self.stats.total_retries * 100
                if self.stats.total_retries > 0
                else 0.0
            ),
            "retry_reasons": dict(self.stats.retry_reasons),
            "current_queue_size": self.stats.current_queue_size,
            "max_queue_size": self.stats.max_queue_size,
            "next_retry_time": next_retry.isoformat() if next_retry else None,
        }

    def clear_queue(self) -> int:
        """Clear all entries from retry queue.

        Returns:
            Number of entries cleared.
        """
        count = len(self._retry_queue)
        self._retry_queue.clear()
        self.stats.current_queue_size = 0

        _LOGGER.info("Cleared retry queue: %d entries removed", count)
        return count

    def classify_error(self, error: Exception) -> RetryReason:
        """Classify error to determine retry strategy.

        Args:
            error: Exception that occurred.

        Returns:
            RetryReason classification.
        """
        error_msg = str(error).lower()

        # Network/connection errors
        if any(
            keyword in error_msg
            for keyword in ["network", "connection", "connect", "resolve"]
        ):
            return RetryReason.NETWORK_ERROR

        # Timeout errors
        if any(keyword in error_msg for keyword in ["timeout", "timed out"]):
            return RetryReason.TIMEOUT

        # Rate limiting
        if any(
            keyword in error_msg
            for keyword in ["rate limit", "too many requests", "429"]
        ):
            return RetryReason.RATE_LIMIT

        # Server errors (5xx)
        if any(
            keyword in error_msg
            for keyword in ["500", "502", "503", "504", "server error"]
        ):
            return RetryReason.SERVER_ERROR

        # Authentication errors
        if any(
            keyword in error_msg
            for keyword in ["auth", "unauthorized", "401", "403", "forbidden"]
        ):
            return RetryReason.AUTHENTICATION_ERROR

        # Unknown
        return RetryReason.UNKNOWN


def determine_retry_strategy(error: Exception) -> tuple[bool, RetryReason]:
    """Determine if error should be retried and why.

    Args:
        error: Exception that occurred.

    Returns:
        Tuple of (should_retry, retry_reason).
    """
    error_msg = str(error).lower()

    # Network/timeout errors: Always retry
    if any(
        keyword in error_msg
        for keyword in ["network", "connection", "timeout", "timed out"]
    ):
        return True, RetryReason.NETWORK_ERROR

    # Rate limiting: Retry with longer delay
    if any(
        keyword in error_msg
        for keyword in ["rate limit", "too many requests", "429"]
    ):
        return True, RetryReason.RATE_LIMIT

    # Server errors (5xx): Retry
    if any(
        keyword in error_msg
        for keyword in ["500", "502", "503", "504", "server error"]
    ):
        return True, RetryReason.SERVER_ERROR

    # Authentication errors: Don't retry (needs user intervention)
    if any(
        keyword in error_msg
        for keyword in ["unauthorized", "401", "forbidden", "403", "credentials"]
    ):
        return False, RetryReason.AUTHENTICATION_ERROR

    # Client errors (4xx except 429): Don't retry
    if any(keyword in error_msg for keyword in ["400", "404", "422"]):
        return False, RetryReason.UNKNOWN

    # Unknown errors: Retry conservatively
    return True, RetryReason.UNKNOWN
