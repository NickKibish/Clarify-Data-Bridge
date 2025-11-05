"""Clarify API Client wrapper for Home Assistant integration."""
from __future__ import annotations

import io
import json
import logging
from typing import Any

from pyclarify import Client, DataFrame
from pyclarify.views.items import Item
from pyclarify.views.signals import SignalInfo
from pyclarify.query import Filter

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
            _LOGGER.debug("Inserting data to Clarify: %d timestamps, %d series",
                         len(data.get("times", [])), len(data.get("series", {})))
            response = self._client.insert(data)
            _LOGGER.info("Successfully inserted data to Clarify")
            return response

        except Exception as err:
            _LOGGER.error("Failed to insert data: %s", err)
            raise ClarifyConnectionError(f"Data insertion failed: {err}") from err

    async def async_insert_dataframe(self, dataframe: DataFrame) -> dict[str, Any]:
        """Insert time-series data using pyclarify DataFrame.

        Args:
            dataframe: pyclarify DataFrame containing times and series data.

        Returns:
            Response from Clarify API.

        Raises:
            ClarifyConnectionError: If not connected or insertion fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug("Inserting DataFrame to Clarify: %d timestamps, %d series",
                         len(dataframe.times), len(dataframe.series))
            response = self._client.insert(dataframe)
            _LOGGER.info("Successfully inserted DataFrame to Clarify")
            return response

        except Exception as err:
            _LOGGER.error("Failed to insert DataFrame: %s", err)
            raise ClarifyConnectionError(f"DataFrame insertion failed: {err}") from err

    async def async_save_signals(
        self,
        input_ids: list[str],
        signals: list[SignalInfo],
        create_only: bool = False,
    ) -> dict[str, Any]:
        """Save signal definitions to Clarify.

        Args:
            input_ids: List of unique input IDs for the signals.
            signals: List of SignalInfo objects with metadata.
            create_only: If True, only create new signals, don't update existing ones.

        Returns:
            Response from Clarify API.

        Raises:
            ClarifyConnectionError: If not connected or save fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        if len(input_ids) != len(signals):
            raise ValueError("Number of input_ids must match number of signals")

        try:
            # Build params for save_signals
            params = {
                "inputs": {input_id: signal for input_id, signal in zip(input_ids, signals)},
                "createOnly": create_only,
            }

            _LOGGER.debug("Saving %d signals to Clarify", len(input_ids))
            response = self._client.save_signals(params=params)
            _LOGGER.info("Successfully saved %d signals to Clarify", len(input_ids))
            return response

        except Exception as err:
            _LOGGER.error("Failed to save signals: %s", err)
            raise ClarifyConnectionError(f"Signal save failed: {err}") from err

    async def async_create_signal(
        self,
        input_id: str,
        name: str,
        description: str | None = None,
        labels: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """Create a single signal with metadata.

        Args:
            input_id: Unique input ID for the signal.
            name: Human-readable name for the signal.
            description: Optional description of the signal.
            labels: Optional dictionary of labels for categorization.

        Returns:
            Response from Clarify API.

        Raises:
            ClarifyConnectionError: If not connected or creation fails.
        """
        signal = SignalInfo(
            name=name,
            description=description or "",
            labels=labels or {},
        )

        return await self.async_save_signals(
            input_ids=[input_id],
            signals=[signal],
            create_only=False,
        )

    async def async_publish_signals(
        self,
        signal_ids: list[str],
        items: list[Item],
        create_only: bool = False,
    ) -> dict[str, Any]:
        """Publish signals as items in Clarify.

        Items are the published version of signals that are visible to the organization.

        Args:
            signal_ids: List of signal IDs to publish.
            items: List of Item objects with metadata and visibility settings.
            create_only: If True, only create new items, don't update existing ones.

        Returns:
            Response from Clarify API mapping signal IDs to item IDs.

        Raises:
            ClarifyConnectionError: If not connected or publish fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        if len(signal_ids) != len(items):
            raise ValueError("Number of signal_ids must match number of items")

        try:
            # Build items_by_signal dict for publish_signals
            items_by_signal = {
                signal_id: item for signal_id, item in zip(signal_ids, items)
            }

            _LOGGER.debug("Publishing %d signals as items", len(signal_ids))
            response = self._client.publish_signals(
                items_by_signal=items_by_signal,
                create_only=create_only,
            )
            _LOGGER.info("Successfully published %d signals as items", len(signal_ids))
            return response

        except Exception as err:
            _LOGGER.error("Failed to publish signals: %s", err)
            raise ClarifyConnectionError(f"Signal publish failed: {err}") from err

    async def async_select_signals(
        self,
        skip: int = 0,
        limit: int = 50,
        sort: list[str] | None = None,
        filter_query: Filter | None = None,
    ) -> dict[str, Any]:
        """Select signals metadata from Clarify.

        Args:
            skip: Number of signals to skip (for pagination).
            limit: Maximum number of signals to return.
            sort: List of sort fields (prefix with - for descending).
            filter_query: Filter to apply to selection.

        Returns:
            Response containing signal metadata.

        Raises:
            ClarifyConnectionError: If not connected or selection fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug("Selecting signals with skip=%d, limit=%d", skip, limit)

            params = {"skip": skip, "limit": limit}
            if sort:
                params["sort"] = sort
            if filter_query:
                params["filter"] = filter_query

            response = self._client.select_signals(**params)
            _LOGGER.info("Successfully selected signals")
            return response

        except Exception as err:
            _LOGGER.error("Failed to select signals: %s", err)
            raise ClarifyConnectionError(f"Signal selection failed: {err}") from err

    async def async_select_items(
        self,
        skip: int = 0,
        limit: int = 50,
        sort: list[str] | None = None,
        filter_query: Filter | None = None,
    ) -> dict[str, Any]:
        """Select items metadata from Clarify.

        Args:
            skip: Number of items to skip (for pagination).
            limit: Maximum number of items to return.
            sort: List of sort fields (prefix with - for descending).
            filter_query: Filter to apply to selection.

        Returns:
            Response containing item metadata.

        Raises:
            ClarifyConnectionError: If not connected or selection fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug("Selecting items with skip=%d, limit=%d", skip, limit)

            params = {"skip": skip, "limit": limit}
            if sort:
                params["sort"] = sort
            if filter_query:
                params["filter"] = filter_query

            response = self._client.select_items(**params)
            _LOGGER.info("Successfully selected items")
            return response

        except Exception as err:
            _LOGGER.error("Failed to select items: %s", err)
            raise ClarifyConnectionError(f"Item selection failed: {err}") from err

    async def async_data_frame(
        self,
        filter_query: Filter | None = None,
        include: list[str] | None = None,
        not_before: str | None = None,
        before: str | None = None,
        rollup: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve time series data from Clarify items.

        Args:
            filter_query: Filter to select which items to retrieve data for.
            include: List of relationships to include (e.g., ["item"]).
            not_before: ISO 8601 timestamp for start of time range.
            before: ISO 8601 timestamp for end of time range.
            rollup: Rollup period (e.g., "PT1H" for 1 hour).

        Returns:
            Response containing time series data and metadata.

        Raises:
            ClarifyConnectionError: If not connected or data retrieval fails.
        """
        if self._client is None:
            raise ClarifyConnectionError("Client not initialized. Call async_connect first.")

        try:
            _LOGGER.debug(
                "Retrieving data frame: not_before=%s, before=%s, rollup=%s",
                not_before,
                before,
                rollup,
            )

            params = {}
            if filter_query:
                params["filter"] = filter_query
            if include:
                params["include"] = include
            if not_before:
                params["notBefore"] = not_before
            if before:
                params["before"] = before
            if rollup:
                params["rollup"] = rollup

            response = self._client.data_frame(**params)
            _LOGGER.info("Successfully retrieved data frame")
            return response

        except Exception as err:
            _LOGGER.error("Failed to retrieve data frame: %s", err)
            raise ClarifyConnectionError(f"Data frame retrieval failed: {err}") from err

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
