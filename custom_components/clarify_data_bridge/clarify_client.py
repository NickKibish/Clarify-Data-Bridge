"""Clarify API Client wrapper for Home Assistant integration."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, TYPE_CHECKING

from pyclarify import Client, DataFrame
from pyclarify.views.items import Item
from pyclarify.views.signals import SignalInfo
from pyclarify.query import Filter

from .credential_manager import create_secure_logger

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = create_secure_logger(__name__)


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
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        integration_id: str,
        api_url: str = "https://api.clarify.cloud/v1/",
    ) -> None:
        """Initialize the Clarify client with OAuth 2.0 credentials.

        Args:
            hass: Home Assistant instance.
            client_id: OAuth 2.0 client ID.
            client_secret: OAuth 2.0 client secret.
            integration_id: Clarify integration ID.
            api_url: Base URL for Clarify API (defaults to production).

        Raises:
            ClarifyAuthenticationError: If credentials are invalid.
            ClarifyConnectionError: If unable to connect to Clarify API.
        """
        self.hass = hass
        self.client_id = client_id
        self.client_secret = client_secret
        self.integration_id = integration_id
        self.api_url = api_url
        self._client: Client | None = None
        self._temp_credentials_file: str | None = None

        _LOGGER.info(
            "Initializing Clarify client: integration_id=%s, api_url=%s",
            integration_id,
            api_url,
        )

    def _create_credentials_file(self) -> str:
        """Create a temporary credentials file for pyclarify.

        Returns:
            Path to temporary credentials file.
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

        _LOGGER.debug(
            "Creating credentials file with apiUrl=%s, integration=%s",
            self.api_url,
            self.integration_id,
        )

        # Create a temporary file that will be cleaned up later
        fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="clarify_creds_")
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(credentials_dict, f, indent=2)

            _LOGGER.debug("Created temporary credentials file: %s", temp_path)
            return temp_path

        except Exception as err:
            # Clean up on error
            try:
                os.close(fd)
                os.unlink(temp_path)
            except:
                pass
            raise ClarifyConnectionError(f"Failed to create credentials file: {err}") from err

    async def async_connect(self) -> bool:
        """Establish connection to Clarify API and verify credentials.

        Returns:
            True if connection successful.

        Raises:
            ClarifyAuthenticationError: If credentials are invalid.
            ClarifyConnectionError: If unable to connect to Clarify API.
        """
        _LOGGER.info("Connecting to Clarify API at %s", self.api_url)

        try:
            # Create credentials file
            self._temp_credentials_file = self._create_credentials_file()
            _LOGGER.debug("Credentials file created successfully")

            # Initialize pyclarify Client with file path
            # Run in executor since Client() may do blocking I/O
            _LOGGER.debug("Initializing pyclarify Client with credentials file: %s", self._temp_credentials_file)
            self._client = await self.hass.async_add_executor_job(
                Client, self._temp_credentials_file
            )
            _LOGGER.info("pyclarify Client initialized successfully")

            # Make an actual API call to verify connection and credentials
            # This will trigger the OAuth 2.0 flow and validate credentials
            # Run in executor since select_signals() makes blocking HTTP calls
            _LOGGER.info("Verifying connection by calling select_signals API")
            try:
                # Use functools.partial to pass keyword arguments to executor
                from functools import partial
                response = await self.hass.async_add_executor_job(
                    partial(self._client.select_signals, skip=0, limit=1)
                )
                _LOGGER.debug("API call successful, response type: %s", type(response))

                # pyclarify returns a Response object, not a dict
                # Just check that we got a response (which means auth worked)
                if response is None:
                    raise ClarifyConnectionError(
                        f"No response from Clarify API. "
                        f"This may indicate an API URL issue. Current URL: {self.api_url}"
                    )

                _LOGGER.info("Successfully connected and authenticated to Clarify API")
                return True

            except Exception as api_err:
                error_msg = str(api_err).lower()
                _LOGGER.error("API call failed: %s", api_err, exc_info=True)

                # Provide specific error messages
                if "401" in error_msg or "unauthorized" in error_msg:
                    raise ClarifyAuthenticationError(
                        f"Authentication failed with Clarify API. "
                        f"Please verify your client_id and client_secret are correct. "
                        f"Error: {api_err}"
                    ) from api_err
                elif "404" in error_msg or "not found" in error_msg:
                    raise ClarifyConnectionError(
                        f"API endpoint not found. This likely means the API URL is incorrect. "
                        f"Current URL: {self.api_url}. "
                        f"Should be: https://api.clarify.cloud/v1/. "
                        f"Error: {api_err}"
                    ) from api_err
                elif "403" in error_msg or "forbidden" in error_msg:
                    raise ClarifyAuthenticationError(
                        f"Access forbidden. Your credentials may not have permission for this operation. "
                        f"Error: {api_err}"
                    ) from api_err
                elif "timeout" in error_msg or "timed out" in error_msg:
                    raise ClarifyConnectionError(
                        f"Connection timeout. Please check your network connection. "
                        f"Error: {api_err}"
                    ) from api_err
                elif "connection" in error_msg or "network" in error_msg:
                    raise ClarifyConnectionError(
                        f"Network connection failed. Please check your internet connection. "
                        f"Error: {api_err}"
                    ) from api_err
                else:
                    raise ClarifyConnectionError(
                        f"Failed to connect to Clarify API at {self.api_url}. "
                        f"Error: {api_err}"
                    ) from api_err

        except (ClarifyAuthenticationError, ClarifyConnectionError):
            # Re-raise our custom exceptions
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error during connection: %s", err, exc_info=True)
            raise ClarifyConnectionError(
                f"Unexpected error connecting to Clarify: {err}"
            ) from err

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
            # Attempt a simple operation to verify connection and credentials
            # This will trigger OAuth flow and validate credentials
            # Run in executor since select_signals() makes blocking HTTP calls
            _LOGGER.debug("Verifying Clarify API connection by selecting signals")

            # Use functools.partial to pass keyword arguments to executor
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(self._client.select_signals, skip=0, limit=1)
            )

            # pyclarify returns a Response object, not a dict
            if response is None:
                raise ClarifyConnectionError("Invalid response from Clarify API")

            _LOGGER.info("Successfully verified Clarify API connection")
            return True

        except Exception as err:
            error_msg = str(err).lower()

            # Categorize errors
            if "auth" in error_msg or "credential" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
                _LOGGER.error("Authentication verification failed: %s", err)
                raise ClarifyAuthenticationError(f"Invalid credentials: {err}") from err
            elif "connect" in error_msg or "network" in error_msg or "timeout" in error_msg:
                _LOGGER.error("Connection verification failed: %s", err)
                raise ClarifyConnectionError(f"Cannot connect to Clarify: {err}") from err
            else:
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
            # Run insert in executor to avoid blocking event loop
            response = await self.hass.async_add_executor_job(
                self._client.insert, data
            )
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
            # Run insert in executor to avoid blocking event loop
            response = await self.hass.async_add_executor_job(
                self._client.insert, dataframe
            )
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
            # Build signals_by_input mapping for the new pyclarify API
            signals_by_input = {input_id: signal for input_id, signal in zip(input_ids, signals)}

            _LOGGER.debug("Saving %d signals to Clarify", len(input_ids))
            # Run save_signals in executor to avoid blocking event loop
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(
                    self._client.save_signals,
                    input_ids=input_ids,
                    signals=signals,
                    signals_by_input=signals_by_input,
                    create_only=create_only,
                    integration=self.integration_id,
                )
            )
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
            # Run publish_signals in executor to avoid blocking event loop
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(
                    self._client.publish_signals,
                    items_by_signal=items_by_signal,
                    create_only=create_only,
                )
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

            # Run select_signals in executor to avoid blocking event loop
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(self._client.select_signals, **params)
            )
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

            # Run select_items in executor to avoid blocking event loop
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(self._client.select_items, **params)
            )
            _LOGGER.info("Successfully selected items")
            return response

        except Exception as err:
            _LOGGER.error("Failed to select items: %s", err)
            raise ClarifyConnectionError(f"Item selection failed: {err}") from err

    async def async_data_frame(
        self,
        filter_query: Filter | None = None,
        include: list[str] | None = None,
        gte: str | None = None,
        lt: str | None = None,
        rollup: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve time series data from Clarify items.

        Args:
            filter_query: Filter to select which items to retrieve data for.
            include: List of relationships to include (e.g., ["item"]).
            gte: ISO 8601 timestamp for start of time range (greater than or equal).
            lt: ISO 8601 timestamp for end of time range (less than).
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
                "Retrieving data frame: gte=%s, lt=%s, rollup=%s",
                gte,
                lt,
                rollup,
            )

            params = {}
            if filter_query:
                params["filter"] = filter_query
            if include:
                params["include"] = include
            if gte:
                params["gte"] = gte
            if lt:
                params["lt"] = lt
            if rollup:
                params["rollup"] = rollup

            # Run data_frame in executor to avoid blocking event loop
            from functools import partial
            response = await self.hass.async_add_executor_job(
                partial(self._client.data_frame, **params)
            )
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

        # Clean up temporary credentials file
        if self._temp_credentials_file is not None:
            try:
                if os.path.exists(self._temp_credentials_file):
                    os.unlink(self._temp_credentials_file)
                    _LOGGER.debug("Cleaned up temporary credentials file: %s", self._temp_credentials_file)
                self._temp_credentials_file = None
            except Exception as err:
                _LOGGER.warning("Failed to clean up temporary credentials file: %s", err)
