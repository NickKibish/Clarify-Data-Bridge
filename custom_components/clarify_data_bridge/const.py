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
DEFAULT_NAME = "Clarify Data Bridge"

# Configuration options
CONF_BATCH_INTERVAL = "batch_interval"
CONF_MAX_BATCH_SIZE = "max_batch_size"
CONF_ENTITY_FILTER = "entity_filter"
CONF_INCLUDE_DOMAINS = "include_domains"
CONF_EXCLUDE_ENTITIES = "exclude_entities"

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

# Service names
SERVICE_PUBLISH_ENTITY = "publish_entity"
SERVICE_PUBLISH_ENTITIES = "publish_entities"
SERVICE_PUBLISH_ALL_TRACKED = "publish_all_tracked"
SERVICE_UPDATE_ITEM_VISIBILITY = "update_item_visibility"
SERVICE_PUBLISH_DOMAIN = "publish_domain"

# Service fields
ATTR_ENTITY_ID = "entity_id"
ATTR_ENTITY_IDS = "entity_ids"
ATTR_VISIBLE = "visible"
ATTR_LABELS = "labels"
ATTR_DOMAIN = "domain"

# Clarify API constants
CLARIFY_API_URL = "https://api.clarify.io/v1"

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
    "temperature",
    "humidity",
    "pressure",
    "battery",
    "power",
    "energy",
    "voltage",
    "current",
    "brightness",
    "speed",
]
