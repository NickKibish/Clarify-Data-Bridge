"""Sensor platform for Clarify Data Bridge."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ENTRY_DATA_CLIENT,
    ENTRY_DATA_DATA_UPDATE_COORDINATOR,
    CONF_INTEGRATION_ID,
)
from .data_update_coordinator import ClarifyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Clarify sensor platform."""
    # Get the data update coordinator from integration data
    coordinator: ClarifyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        ENTRY_DATA_DATA_UPDATE_COORDINATOR
    ]

    integration_id = entry.data[CONF_INTEGRATION_ID]

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Create sensors for each available item
    entities = []

    for item_id in coordinator.available_items:
        metadata = coordinator.get_item_metadata(item_id)

        if metadata:
            # Create latest value sensor
            entities.append(
                ClarifyItemSensor(
                    coordinator=coordinator,
                    item_id=item_id,
                    integration_id=integration_id,
                    sensor_type="latest",
                )
            )

            # Create average sensor
            entities.append(
                ClarifyItemSensor(
                    coordinator=coordinator,
                    item_id=item_id,
                    integration_id=integration_id,
                    sensor_type="average",
                )
            )

            # Create min/max sensors
            entities.append(
                ClarifyItemSensor(
                    coordinator=coordinator,
                    item_id=item_id,
                    integration_id=integration_id,
                    sensor_type="min",
                )
            )

            entities.append(
                ClarifyItemSensor(
                    coordinator=coordinator,
                    item_id=item_id,
                    integration_id=integration_id,
                    sensor_type="max",
                )
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d Clarify sensors", len(entities))
    else:
        _LOGGER.warning("No Clarify items found to create sensors")


class ClarifyItemSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing a Clarify item's data."""

    def __init__(
        self,
        coordinator: ClarifyDataUpdateCoordinator,
        item_id: str,
        integration_id: str,
        sensor_type: str = "latest",
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data update coordinator.
            item_id: Clarify item ID.
            integration_id: Integration ID for unique naming.
            sensor_type: Type of sensor (latest, average, min, max).
        """
        super().__init__(coordinator)

        self.item_id = item_id
        self.integration_id = integration_id
        self.sensor_type = sensor_type

        # Get metadata
        metadata = coordinator.get_item_metadata(item_id)
        self._name = metadata.get("name", item_id) if metadata else item_id
        self._unit = metadata.get("unit") if metadata else None

        # Generate unique ID
        self._attr_unique_id = f"clarify_{integration_id}_{item_id}_{sensor_type}"

        # Set entity ID
        safe_name = self._name.lower().replace(" ", "_").replace("-", "_")
        self._attr_name = f"{self._name} ({sensor_type.capitalize()})"
        self.entity_id = f"sensor.clarify_{safe_name}_{sensor_type}"

        # Set state class
        if sensor_type in ("latest", "average"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_state_class = None

        _LOGGER.debug(
            "Created Clarify sensor: %s (item_id: %s, type: %s)",
            self._attr_name,
            item_id,
            sensor_type,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.sensor_type == "latest":
            return self.coordinator.get_latest_value(self.item_id)
        elif self.sensor_type == "average":
            return self.coordinator.get_average_value(self.item_id)
        elif self.sensor_type == "min":
            return self.coordinator.get_min_value(self.item_id)
        elif self.sensor_type == "max":
            return self.coordinator.get_max_value(self.item_id)
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        metadata = self.coordinator.get_item_metadata(self.item_id)
        item_data = self.coordinator.get_item_data(self.item_id)

        attributes = {
            "item_id": self.item_id,
            "sensor_type": self.sensor_type,
            "integration_id": self.integration_id,
        }

        if metadata:
            attributes["description"] = metadata.get("description", "")
            attributes["labels"] = metadata.get("labels", {})

        if item_data:
            attributes["data_points"] = len(item_data)

            # Add timestamps for latest value
            if self.sensor_type == "latest" and item_data:
                latest_timestamp = max(item_data.keys())
                attributes["last_updated"] = latest_timestamp

        # Add additional stats
        if self.sensor_type == "average":
            attributes["min_value"] = self.coordinator.get_min_value(self.item_id)
            attributes["max_value"] = self.coordinator.get_max_value(self.item_id)
        elif self.sensor_type == "latest":
            attributes["average"] = self.coordinator.get_average_value(self.item_id)

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.item_id in self.coordinator.available_items
            and self.native_value is not None
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        metadata = self.coordinator.get_item_metadata(self.item_id)
        name = metadata.get("name", "Clarify Item") if metadata else "Clarify Item"

        return {
            "identifiers": {(DOMAIN, f"{self.integration_id}_{self.item_id}")},
            "name": name,
            "manufacturer": "Clarify",
            "model": "Clarify Item",
            "via_device": (DOMAIN, self.integration_id),
        }
