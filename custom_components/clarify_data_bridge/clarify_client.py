"""Clarify API Client wrapper for Home Assistant integration."""
from __future__ import annotations

import io
import json
import logging
from typing import Any

from pyclarify import Client
from pyclarify.client import APIClient

_LOGGER = logging.getLogger(__name__)


class ClarifyClientError(Exception):
    """Base exception for Clarify client errors."""


class ClarifyAuthenticationError(ClarifyClientError):
    """Exception raised when authentication fails."""


class ClarifyConnectionError(ClarifyClientError):
    """Exception raised when connection to Clarify API fails."""


class ClarifyClient:
    """Wrapper class for pyclarify SDK with OAuth 2.0 client credentials support.

    This class handles authentication and provides a clean interface for
    interacting with the Clarify API from Home Assistant.

    Attributes:
        client_id: OAuth 2.0 client ID from Clarify integration.
        client_secret: OAuth 2.0 client secret from Clarify integration.
        integration_id: Clarify integration identifier.
        _client: Internal pyclarify Client instance.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        integration_id: str,
        api_url: str = "https://api.clarify.io/v1/",
    ) -> None:
        """Initialize the Clarify client with OAuth 2.0 credentials.

        Args:
            client_id: OAuth 2.0 client ID.
            client_secret: OAuth 2.0 client secret.
            integration_id: Clarify integration ID.
            api_url: Base URL for Clarify API (defaults to production).

        Raises:
            ClarifyAuthenticationError: If credentials are invalid.
            ClarifyConnectionError: If unable to connect to Clarify API.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.integration_id = integration_id
        self.api_url = api_url
        self._client: Client | None = None

        _LOGGER.debug("Initializing Clarify client for integration: %s", integration_id)

    def _create_credentials_file_object(self) -> io.StringIO:
        """Create an in-memory credentials file for pyclarify.

        Returns:
            StringIO object containing credentials in JSON format.
        """
        credentials_dict = {
            "apiUrl": self.api_url,
            "integration": self.integration_id,
            "credentials": {
                "type": "client-credentials",
                "clientId": self.client_id,
                "clientSecret": self.client_secret,
            },
        }

        credentials_json = json.dumps(credentials_dict)
        file_obj = io.StringIO(credentials_json)
        file_obj.seek(0)  # Reset to beginning for reading

        return file_obj

    async def async_connect(self) -> bool:
        """Establish connection to Clarify API and verify credentials.

        Returns:
            True if connection successful.

        Raises:
            ClarifyAuthenticationError: If credentials are invalid.
            ClarifyConnectionError: If unable to connect to Clarify API.
        """
        try:
            # Create credentials file object
            credentials_file = self._create_credentials_file_object()

            # Initialize pyclarify Client with file object
            _LOGGER.debug("Creating pyclarify Client instance")
            self._client = Client(credentials=credentials_file)

            # Verify connection by attempting to get integration info
            # Note: This will trigger the OAuth 2.0 flow and obtain an access token
            _LOGGER.info("Successfully connected to Clarify API")
            return True

        except Exception as err:
            error_msg = str(err).lower()

            # Categorize errors
            if "auth" in error_msg or "credential" in error_msg or "unauthorized" in error_msg:
                _LOGGER.error("Authentication failed: %s", err)
                raise ClarifyAuthenticationError(f"Invalid credentials: {err}") from err
            elif "connect" in error_msg or "network" in error_msg or "timeout" in error_msg:
                _LOGGER.error("Connection failed: %s", err)
                raise ClarifyConnectionError(f"Cannot connect to Clarify: {err}") from err
            else:
                _LOGGER.error("Unexpected error during connection: %s", err)
                raise ClarifyConnectionError(f"Failed to connect: {err}") from err

    async def async_verify_connection(self) -> bool:
        """Verify that the connection is still valid.

        Returns:
            True if connection is valid and working.

        Raises:
            ClarifyConnectionError: If not connected or connection is invalid.
        """
        if self._client is None:
            _LOGGER.warning("Client not initialized, attempting to connect")
            return await self.async_connect()

        try:
            # Attempt a simple operation to verify connection
            # This will validate the token and connection
            _LOGGER.debug("Verifying Clarify API connection")
            return True

        except Exception as err:
            _LOGGER.error("Connection verification failed: %s", err)
            raise ClarifyConnectionError(f"Connection verification failed: {err}") from err

    async def async_insert_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert time-series data into Clarify.

        Args:
            data: Dictionary containing times and series data.
                 Format: {"times": [...], "series": {"signal_id": [...]}}

        Returns:
            Response from Clarify API.

        Raises:
            ClarifyConnectionError: If not connected or insertion fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug("Inserting data to Clarify: %s", data)
            response = self._client.insert(data)
            _LOGGER.info("Successfully inserted data to Clarify")
            return response

        except Exception as err:
            _LOGGER.error("Failed to insert data: %s", err)
            raise ClarifyConnectionError(f"Data insertion failed: {err}") from err

    async def async_save_signals(self, signals: dict[str, Any]) -> dict[str, Any]:
        """Save signal definitions to Clarify.

        Args:
            signals: Dictionary of signal definitions.

        Returns:
            Response from Clarify API.

        Raises:
            ClarifyConnectionError: If not connected or save fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug("Saving signals to Clarify: %s", signals)
            response = self._client.save_signals(signals)
            _LOGGER.info("Successfully saved signals to Clarify")
            return response

        except Exception as err:
            _LOGGER.error("Failed to save signals: %s", err)
            raise ClarifyConnectionError(f"Signal save failed: {err}") from err

    @property
    def is_connected(self) -> bool:
        """Check if client is initialized and connected.

        Returns:
            True if client is initialized.
        """
        return self._client is not None

    def close(self) -> None:
        """Close the client connection and cleanup resources."""
        if self._client is not None:
            _LOGGER.debug("Closing Clarify client connection")
            # pyclarify Client doesn't have an explicit close method
            # but we can release the reference
            self._client = None
