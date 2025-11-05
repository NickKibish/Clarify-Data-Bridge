"""Constants for the Clarify Data Bridge integration."""

# Integration domain
DOMAIN = "clarify_data_bridge"

# Configuration keys (OAuth 2.0 Client Credentials)
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_INTEGRATION_ID = "integration_id"
CONF_UPDATE_INTERVAL = "update_interval"

# Legacy configuration keys (for migration compatibility)
CONF_API_KEY = "api_key"

# Default values
DEFAULT_UPDATE_INTERVAL = 60  # seconds
DEFAULT_BATCH_INTERVAL = 300  # 5 minutes - batch data insertion interval
DEFAULT_MAX_BATCH_SIZE = 100  # Maximum number of data points per batch
DEFAULT_DATA_UPDATE_INTERVAL = 300  # 5 minutes - data retrieval interval
DEFAULT_LOOKBACK_HOURS = 24  # Hours of historical data to retrieve
DEFAULT_NAME = "Clarify Data Bridge"
DEFAULT_PUBLISHING_STRATEGY = "manual"  # Don't auto-publish by default
DEFAULT_AUTO_PUBLISH = False
DEFAULT_VISIBLE = True

# Configuration options
CONF_BATCH_INTERVAL = "batch_interval"
CONF_MAX_BATCH_SIZE = "max_batch_size"
CONF_ENTITY_FILTER = "entity_filter"
CONF_INCLUDE_DOMAINS = "include_domains"
CONF_EXCLUDE_ENTITIES = "exclude_entities"
CONF_INCLUDE_DEVICE_CLASSES = "include_device_classes"
CONF_EXCLUDE_DEVICE_CLASSES = "exclude_device_classes"
CONF_INCLUDE_PATTERNS = "include_patterns"
CONF_EXCLUDE_PATTERNS = "exclude_patterns"
CONF_MIN_PRIORITY = "min_priority"
CONF_AUTO_DISCOVER = "auto_discover"
CONF_PUBLISH_ON_DISCOVERY = "publish_on_discovery"

# Publishing options
CONF_PUBLISHING_STRATEGY = "publishing_strategy"
CONF_PUBLISHING_RULES = "publishing_rules"
CONF_AUTO_PUBLISH = "auto_publish"
CONF_DEFAULT_VISIBLE = "default_visible"
CONF_PUBLISH_PRIORITIES = "publish_priorities"
CONF_PUBLISH_DEVICE_CLASSES = "publish_device_classes"
CONF_PUBLISH_CATEGORIES = "publish_categories"

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"

# Entry data keys
ENTRY_DATA_CLIENT = "client"
ENTRY_DATA_COORDINATOR = "coordinator"
ENTRY_DATA_LISTENER = "listener"
ENTRY_DATA_SIGNAL_MANAGER = "signal_manager"
ENTRY_DATA_ITEM_MANAGER = "item_manager"
ENTRY_DATA_DATA_UPDATE_COORDINATOR = "data_update_coordinator"

# Service names
SERVICE_PUBLISH_ENTITY = "publish_entity"
SERVICE_PUBLISH_ENTITIES = "publish_entities"
SERVICE_PUBLISH_ALL_TRACKED = "publish_all_tracked"
SERVICE_UPDATE_ITEM_VISIBILITY = "update_item_visibility"
SERVICE_PUBLISH_DOMAIN = "publish_domain"
SERVICE_PUBLISH_BY_PRIORITY = "publish_by_priority"
SERVICE_PUBLISH_BY_DEVICE_CLASS = "publish_by_device_class"
SERVICE_UNPUBLISH_ENTITY = "unpublish_entity"
SERVICE_SYNC_PUBLISHING = "sync_publishing"

# Service fields
ATTR_ENTITY_ID = "entity_id"
ATTR_ENTITY_IDS = "entity_ids"
ATTR_VISIBLE = "visible"
ATTR_LABELS = "labels"
ATTR_DOMAIN = "domain"
ATTR_PRIORITY = "priority"
ATTR_DEVICE_CLASS = "device_class"
ATTR_DEVICE_CLASSES = "device_classes"
ATTR_STRATEGY = "strategy"
ATTR_FORCE = "force"

# Clarify API constants
CLARIFY_API_URL = "https://api.clarify.cloud/v1"

# Supported Home Assistant domains for data collection
SUPPORTED_DOMAINS = [
    "sensor",
    "binary_sensor",
    "light",
    "switch",
    "climate",
    "cover",
    "fan",
    "lock",
    "media_player",
    "weather",
]

# State attributes to track
NUMERIC_ATTRIBUTES = [
    # Temperature
    "temperature",
    "current_temperature",
    "target_temperature",
    "target_temp_high",
    "target_temp_low",
    # Climate
    "humidity",
    "current_humidity",
    "target_humidity",
    "pressure",
    "wind_speed",
    "wind_bearing",
    # Power & Energy
    "power",
    "energy",
    "voltage",
    "current",
    "power_factor",
    "apparent_power",
    "reactive_power",
    # Battery
    "battery",
    "battery_level",
    # Light
    "brightness",
    "color_temp",
    "kelvin",
    # Media
    "volume_level",
    "media_position",
    # HVAC
    "fan_speed",
    # Other
    "speed",
    "position",
    "tilt_position",
]

# High priority device classes for time-series data
HIGH_PRIORITY_DEVICE_CLASSES = {
    # Energy & Power
    "energy",
    "power",
    "apparent_power",
    "reactive_power",
    "power_factor",
    "voltage",
    "current",
    "energy_storage",
    # Environmental
    "temperature",
    "humidity",
    "pressure",
    "atmospheric_pressure",
    "pm25",
    "pm10",
    "carbon_dioxide",
    "carbon_monoxide",
    "aqi",
    "gas",
    "nitrogen_dioxide",
    "nitrogen_monoxide",
    "ozone",
    "sulphur_dioxide",
    "volatile_organic_compounds",
    # Resource monitoring
    "battery",
    "data_rate",
    "data_size",
    "frequency",
    "monetary",
    "weight",
}

# Medium priority device classes
MEDIUM_PRIORITY_DEVICE_CLASSES = {
    "illuminance",
    "distance",
    "speed",
    "duration",
    "brightness",
    "volume",
    "sound_pressure",
    "signal_strength",
    "timestamp",
}

# Device classes for binary sensors (convertible to 0/1)
BINARY_DEVICE_CLASSES = {
    "battery_charging",
    "cold",
    "connectivity",
    "door",
    "garage_door",
    "gas",
    "heat",
    "light",
    "lock",
    "moisture",
    "motion",
    "moving",
    "occupancy",
    "opening",
    "plug",
    "power",
    "presence",
    "problem",
    "running",
    "safety",
    "smoke",
    "sound",
    "tamper",
    "update",
    "vibration",
    "window",
}
