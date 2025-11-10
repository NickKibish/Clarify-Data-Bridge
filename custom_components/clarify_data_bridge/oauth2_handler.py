"""OAuth 2.0 token management and refresh handling for Clarify integration.

This module provides automatic token refresh and lifecycle management for
OAuth 2.0 client credentials flow.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

from .credential_manager import (
    CredentialManager,
    OAuth2Credentials,
    CredentialStatus,
    create_secure_logger,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = create_secure_logger(__name__)

# Token refresh settings
TOKEN_REFRESH_BUFFER_MINUTES = 5  # Refresh 5 minutes before expiration
TOKEN_CHECK_INTERVAL_SECONDS = 300  # Check tokens every 5 minutes
MAX_REFRESH_RETRIES = 3
REFRESH_RETRY_DELAY_SECONDS = 30


class TokenRefreshError(Exception):
    """Exception raised when token refresh fails."""


class OAuth2TokenManager:
    """Manages OAuth 2.0 token lifecycle and automatic refresh.

    This class monitors token expiration and automatically refreshes tokens
    before they expire to ensure uninterrupted API access.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        credential_manager: CredentialManager,
    ) -> None:
        """Initialize token manager.

        Args:
            hass: Home Assistant instance
            credential_manager: Credential manager instance
        """
        self.hass = hass
        self.credential_manager = credential_manager
        self._refresh_tasks: dict[str, asyncio.Task] = {}
        self._refresh_callbacks: dict[str, list[Callable]] = {}
        self._is_running = False

        _LOGGER.info("OAuth 2.0 token manager initialized")

    async def async_start(self) -> None:
        """Start token refresh monitoring."""
        if self._is_running:
            _LOGGER.warning("Token manager already running")
            return

        self._is_running = True
        _LOGGER.info("Starting token refresh monitoring")

        # Start monitoring task
        self.hass.async_create_task(self._async_monitor_tokens())

    async def async_stop(self) -> None:
        """Stop token refresh monitoring."""
        self._is_running = False
        _LOGGER.info("Stopping token refresh monitoring")

        # Cancel all refresh tasks
        for task in self._refresh_tasks.values():
            task.cancel()

        self._refresh_tasks.clear()

    async def async_register_credentials(
        self,
        entry_id: str,
        credentials: OAuth2Credentials,
    ) -> None:
        """Register credentials for automatic token refresh.

        Args:
            entry_id: Config entry ID
            credentials: OAuth 2.0 credentials
        """
        _LOGGER.info(
            "Registering credentials for automatic refresh: entry=%s",
            self.credential_manager._mask_entry_id(entry_id),
        )

        # Store credentials
        await self.credential_manager.async_store_credentials(entry_id, credentials)

        # Start monitoring if needed
        if not self._is_running:
            await self.async_start()

    async def async_unregister_credentials(self, entry_id: str) -> None:
        """Unregister credentials from token refresh.

        Args:
            entry_id: Config entry ID
        """
        _LOGGER.info(
            "Unregistering credentials: entry=%s",
            self.credential_manager._mask_entry_id(entry_id),
        )

        # Cancel refresh task if running
        if entry_id in self._refresh_tasks:
            self._refresh_tasks[entry_id].cancel()
            del self._refresh_tasks[entry_id]

        # Remove callbacks
        if entry_id in self._refresh_callbacks:
            del self._refresh_callbacks[entry_id]

        # Delete credentials
        await self.credential_manager.async_delete_credentials(entry_id)

    def register_refresh_callback(
        self, entry_id: str, callback: Callable
    ) -> None:
        """Register callback to be called after successful token refresh.

        Args:
            entry_id: Config entry ID
            callback: Async callback function
        """
        if entry_id not in self._refresh_callbacks:
            self._refresh_callbacks[entry_id] = []

        self._refresh_callbacks[entry_id].append(callback)
        _LOGGER.debug("Registered refresh callback for entry: %s", entry_id[:8])

    async def _async_monitor_tokens(self) -> None:
        """Monitor tokens and trigger refresh when needed."""
        _LOGGER.info("Token monitoring started")

        while self._is_running:
            try:
                # Get all credentials
                credentials_dict = self.credential_manager._credentials

                for entry_id, credentials in credentials_dict.items():
                    # Check if token needs refresh
                    if self._should_refresh_token(credentials):
                        _LOGGER.info(
                            "Token expiring soon for entry %s, triggering refresh",
                            self.credential_manager._mask_entry_id(entry_id),
                        )

                        # Start refresh task if not already running
                        if entry_id not in self._refresh_tasks or self._refresh_tasks[entry_id].done():
                            self._refresh_tasks[entry_id] = self.hass.async_create_task(
                                self._async_refresh_token(entry_id, credentials)
                            )

                # Sleep before next check
                await asyncio.sleep(TOKEN_CHECK_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                _LOGGER.info("Token monitoring cancelled")
                break
            except Exception as err:
                _LOGGER.error("Error in token monitoring: %s", err, exc_info=True)
                await asyncio.sleep(TOKEN_CHECK_INTERVAL_SECONDS)

        _LOGGER.info("Token monitoring stopped")

    def _should_refresh_token(self, credentials: OAuth2Credentials) -> bool:
        """Check if token should be refreshed.

        Args:
            credentials: Credentials to check

        Returns:
            True if token should be refreshed
        """
        # If no token exists, no need to refresh (will be obtained on first API call)
        if not credentials.access_token or not credentials.token_expires_at:
            return False

        # Check if token expires soon
        time_until_expiry = credentials.token_expires_at - datetime.utcnow()
        should_refresh = time_until_expiry <= timedelta(
            minutes=TOKEN_REFRESH_BUFFER_MINUTES
        )

        if should_refresh:
            _LOGGER.debug(
                "Token expires in %s, refresh needed",
                time_until_expiry,
            )

        return should_refresh

    async def _async_refresh_token(
        self, entry_id: str, credentials: OAuth2Credentials
    ) -> bool:
        """Refresh OAuth 2.0 access token.

        Args:
            entry_id: Config entry ID
            credentials: Current credentials

        Returns:
            True if refresh successful
        """
        _LOGGER.info(
            "Refreshing token for entry: %s",
            self.credential_manager._mask_entry_id(entry_id),
        )

        for attempt in range(1, MAX_REFRESH_RETRIES + 1):
            try:
                # Import here to avoid circular dependency
                from .clarify_client import ClarifyClient

                # Create client with current credentials
                client = ClarifyClient(
                    hass=self.hass,
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                    integration_id=credentials.integration_id,
                )

                # Connect (this will obtain new token via OAuth 2.0 flow)
                await client.async_connect()

                # pyclarify handles token refresh internally during connect
                # We just need to validate the connection worked
                await client.async_verify_connection()

                _LOGGER.info(
                    "Token refresh successful for entry: %s",
                    self.credential_manager._mask_entry_id(entry_id),
                )

                # Update last validated time
                credentials.last_validated = datetime.utcnow()
                await self.credential_manager.async_save()

                # Call registered callbacks
                await self._async_call_refresh_callbacks(entry_id)

                return True

            except Exception as err:
                _LOGGER.error(
                    "Token refresh attempt %d/%d failed: %s",
                    attempt,
                    MAX_REFRESH_RETRIES,
                    err,
                )

                if attempt < MAX_REFRESH_RETRIES:
                    # Wait before retry
                    await asyncio.sleep(REFRESH_RETRY_DELAY_SECONDS)
                else:
                    # All retries exhausted
                    _LOGGER.error(
                        "Token refresh failed after %d attempts for entry: %s",
                        MAX_REFRESH_RETRIES,
                        self.credential_manager._mask_entry_id(entry_id),
                    )
                    raise TokenRefreshError(
                        f"Failed to refresh token after {MAX_REFRESH_RETRIES} attempts"
                    ) from err

        return False

    async def _async_call_refresh_callbacks(self, entry_id: str) -> None:
        """Call registered callbacks after successful refresh.

        Args:
            entry_id: Config entry ID
        """
        if entry_id not in self._refresh_callbacks:
            return

        callbacks = self._refresh_callbacks[entry_id]
        _LOGGER.debug(
            "Calling %d refresh callback(s) for entry: %s",
            len(callbacks),
            self.credential_manager._mask_entry_id(entry_id),
        )

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as err:
                _LOGGER.error("Error in refresh callback: %s", err, exc_info=True)

    async def async_force_refresh(self, entry_id: str) -> bool:
        """Force immediate token refresh.

        Args:
            entry_id: Config entry ID

        Returns:
            True if refresh successful
        """
        credentials = await self.credential_manager.async_get_credentials(entry_id)
        if not credentials:
            _LOGGER.error(
                "Cannot force refresh - credentials not found for entry: %s",
                self.credential_manager._mask_entry_id(entry_id),
            )
            return False

        _LOGGER.info(
            "Forcing token refresh for entry: %s",
            self.credential_manager._mask_entry_id(entry_id),
        )

        return await self._async_refresh_token(entry_id, credentials)

    def get_token_status(self, entry_id: str) -> dict[str, any]:
        """Get token status information.

        Args:
            entry_id: Config entry ID

        Returns:
            Token status dictionary
        """
        credentials = self.credential_manager._credentials.get(entry_id)
        if not credentials:
            return {
                "exists": False,
                "message": "Credentials not found",
            }

        status = {
            "exists": True,
            "has_token": credentials.access_token is not None,
            "token_expired": credentials.is_token_expired(),
        }

        if credentials.token_expires_at:
            time_until_expiry = credentials.token_expires_at - datetime.utcnow()
            status["expires_at"] = credentials.token_expires_at.isoformat()
            status["time_until_expiry_seconds"] = int(time_until_expiry.total_seconds())
            status["expires_soon"] = self._should_refresh_token(credentials)

        if entry_id in self._refresh_tasks:
            task = self._refresh_tasks[entry_id]
            status["refresh_in_progress"] = not task.done()

        return status


class CredentialValidator:
    """Validates credentials and provides detailed error messages."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize validator.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass

    async def async_validate_and_test(
        self,
        client_id: str,
        client_secret: str,
        integration_id: str,
        api_url: str | None = None,
    ) -> tuple[bool, str, dict[str, any]]:
        """Validate credentials format and test connection.

        Args:
            client_id: Client ID
            client_secret: Client secret
            integration_id: Integration ID
            api_url: Optional API URL (defaults to dev server if not provided)

        Returns:
            Tuple of (is_valid, error_message, details)
        """
        details = {}

        # Step 1: Format validation
        from .credential_manager import CredentialManager

        manager = CredentialManager(self.hass)
        is_valid_format, format_error = manager.validate_credential_format(
            client_id, client_secret, integration_id
        )

        if not is_valid_format:
            return False, format_error, {"step": "format_validation"}

        details["format_validation"] = "passed"

        # Step 2: Create credentials
        credentials = OAuth2Credentials(
            client_id=client_id,
            client_secret=client_secret,
            integration_id=integration_id,
        )

        # Step 3: Test connection
        try:
            result = await manager.async_validate_credentials(credentials, api_url)

            if result.is_valid:
                details["connection_test"] = "passed"
                details["status"] = result.status.value
                return True, "Credentials validated successfully", details
            else:
                details["connection_test"] = "failed"
                details["status"] = result.status.value
                details["error_details"] = result.error_details
                return False, result.message, details

        except Exception as err:
            details["connection_test"] = "failed"
            details["exception"] = str(err)
            return False, f"Connection test failed: {str(err)}", details


async def async_setup_oauth2_manager(
    hass: HomeAssistant,
) -> tuple[CredentialManager, OAuth2TokenManager]:
    """Set up OAuth 2.0 management components.

    Args:
        hass: Home Assistant instance

    Returns:
        Tuple of (credential_manager, token_manager)
    """
    # Create credential manager
    credential_manager = CredentialManager(hass)
    await credential_manager.async_load()

    # Create token manager
    token_manager = OAuth2TokenManager(hass, credential_manager)

    _LOGGER.info("OAuth 2.0 management components initialized")

    return credential_manager, token_manager
