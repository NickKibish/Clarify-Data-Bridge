"""Data update coordinator for retrieving data from Clarify."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from pyclarify.query import Filter, Regex

from .clarify_client import ClarifyClient, ClarifyConnectionError

_LOGGER = logging.getLogger(__name__)


class ClarifyDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching data from Clarify.

    This coordinator periodically fetches time series data from Clarify
    and makes it available to sensor entities.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ClarifyClient,
        integration_id: str,
        update_interval: timedelta,
        lookback_hours: int = 24,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            client: ClarifyClient for API communication.
            integration_id: Integration ID for filtering items.
            update_interval: How often to fetch data.
            lookback_hours: How many hours of data to retrieve.
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Clarify Data Update",
            update_interval=update_interval,
        )

        self.client = client
        self.integration_id = integration_id
        self.lookback_hours = lookback_hours

        # Store latest data: {item_id: {timestamp: value}}
        self._items_data: dict[str, dict[str, Any]] = {}

        # Store item metadata: {item_id: metadata}
        self._items_metadata: dict[str, dict[str, Any]] = {}

        _LOGGER.debug(
            "Initialized ClarifyDataUpdateCoordinator with update_interval=%s, lookback_hours=%d",
            update_interval,
            lookback_hours,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Clarify.

        Returns:
            Dictionary containing items data and metadata.

        Raises:
            UpdateFailed: If data fetch fails.
        """
        try:
            # Calculate time range
            now = dt_util.utcnow()
            not_before = now - timedelta(hours=self.lookback_hours)

            # Build filter to only get our integration's items
            filter_query = Filter(
                fields={
                    "labels.integration": Regex(value=self.integration_id)
                }
            )

            _LOGGER.debug(
                "Fetching Clarify data from %s to %s",
                not_before.isoformat(),
                now.isoformat(),
            )

            # Fetch data from Clarify
            response = await self.client.async_data_frame(
                filter_query=filter_query,
                include=["item"],
                not_before=not_before.isoformat(),
                before=now.isoformat(),
                rollup=None,  # No aggregation, get raw data
            )

            # Parse response
            items_data = {}
            items_metadata = {}

            if "data" in response:
                data = response["data"]

                # Extract times
                times = data.get("times", [])

                # Extract series data
                series = data.get("series", {})

                for item_id, values in series.items():
                    # Store time series for this item
                    item_series = {}
                    for i, timestamp in enumerate(times):
                        if i < len(values) and values[i] is not None:
                            item_series[timestamp] = values[i]

                    items_data[item_id] = item_series

            # Extract metadata if included
            if "included" in response and "items" in response["included"]:
                for item_id, item_data in response["included"]["items"].items():
                    items_metadata[item_id] = {
                        "name": item_data.get("name", "Unknown"),
                        "description": item_data.get("description", ""),
                        "labels": item_data.get("labels", {}),
                        "unit": self._extract_unit(item_data),
                    }

            # Update stored data
            self._items_data = items_data
            self._items_metadata = items_metadata

            _LOGGER.info(
                "Successfully fetched data for %d items from Clarify",
                len(items_data),
            )

            return {
                "items_data": items_data,
                "items_metadata": items_metadata,
                "last_update": now,
            }

        except ClarifyConnectionError as err:
            _LOGGER.error("Failed to fetch data from Clarify: %s", err)
            raise UpdateFailed(f"Error fetching Clarify data: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Clarify data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _extract_unit(self, item_data: dict[str, Any]) -> str | None:
        """Extract unit of measurement from item metadata.

        Args:
            item_data: Item metadata from Clarify.

        Returns:
            Unit string or None.
        """
        labels = item_data.get("labels", {})

        # Try to get unit from labels
        if "unit" in labels and labels["unit"]:
            return labels["unit"][0] if isinstance(labels["unit"], list) else labels["unit"]

        return None

    def get_item_data(self, item_id: str) -> dict[str, Any] | None:
        """Get time series data for a specific item.

        Args:
            item_id: Clarify item ID.

        Returns:
            Dictionary of {timestamp: value} or None.
        """
        return self._items_data.get(item_id)

    def get_item_metadata(self, item_id: str) -> dict[str, Any] | None:
        """Get metadata for a specific item.

        Args:
            item_id: Clarify item ID.

        Returns:
            Item metadata dictionary or None.
        """
        return self._items_metadata.get(item_id)

    def get_latest_value(self, item_id: str) -> float | None:
        """Get the latest value for an item.

        Args:
            item_id: Clarify item ID.

        Returns:
            Latest value or None.
        """
        item_data = self.get_item_data(item_id)
        if not item_data:
            return None

        # Get the latest timestamp
        if not item_data:
            return None

        latest_timestamp = max(item_data.keys())
        return item_data[latest_timestamp]

    def get_average_value(self, item_id: str) -> float | None:
        """Get the average value for an item over the time range.

        Args:
            item_id: Clarify item ID.

        Returns:
            Average value or None.
        """
        item_data = self.get_item_data(item_id)
        if not item_data:
            return None

        values = list(item_data.values())
        if not values:
            return None

        return sum(values) / len(values)

    def get_min_value(self, item_id: str) -> float | None:
        """Get the minimum value for an item.

        Args:
            item_id: Clarify item ID.

        Returns:
            Minimum value or None.
        """
        item_data = self.get_item_data(item_id)
        if not item_data:
            return None

        values = list(item_data.values())
        return min(values) if values else None

    def get_max_value(self, item_id: str) -> float | None:
        """Get the maximum value for an item.

        Args:
            item_id: Clarify item ID.

        Returns:
            Maximum value or None.
        """
        item_data = self.get_item_data(item_id)
        if not item_data:
            return None

        values = list(item_data.values())
        return max(values) if values else None

    @property
    def available_items(self) -> list[str]:
        """Get list of available item IDs.

        Returns:
            List of item IDs with data.
        """
        return list(self._items_data.keys())

    @property
    def item_count(self) -> int:
        """Get number of items with data.

        Returns:
            Count of items.
        """
        return len(self._items_data)
