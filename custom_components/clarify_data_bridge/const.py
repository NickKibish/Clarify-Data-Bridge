"""Constants for the Clarify Data Bridge integration."""

# Integration domain
DOMAIN = "clarify_data_bridge"

# Configuration keys (OAuth 2.0 Client Credentials)
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_INTEGRATION_ID = "integration_id"
CONF_DEV_MODE = "dev_mode"
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

# Buffering strategy options
DEFAULT_BUFFER_STRATEGY = "hybrid"  # Options: time, size, hybrid, adaptive
DEFAULT_STALE_THRESHOLD_MINUTES = 5  # Data older than this is considered stale
DEFAULT_VALIDATE_RANGES = True  # Validate numeric ranges based on device class
DEFAULT_TRACK_CHANGES_ONLY = False  # Track all data or only changes

# Retry and transmission options
DEFAULT_MAX_RETRY_ATTEMPTS = 5  # Maximum retry attempts for failed transmissions
DEFAULT_RETRY_BASE_DELAY = 2.0  # Base delay in seconds for exponential backoff
DEFAULT_RETRY_MAX_DELAY = 300.0  # Maximum delay between retries (5 minutes)
DEFAULT_RETRY_QUEUE_SIZE = 1000  # Maximum number of entries in retry queue
DEFAULT_TRANSMISSION_HISTORY_SIZE = 100  # Number of transmission records to keep

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
CONF_SELECTED_ENTITIES = "selected_entities"
CONF_AUTO_DISCOVER = "auto_discover"
CONF_PUBLISH_ON_DISCOVERY = "publish_on_discovery"

# Buffering configuration
CONF_BUFFER_STRATEGY = "buffer_strategy"
CONF_STALE_THRESHOLD = "stale_threshold_minutes"
CONF_VALIDATE_RANGES = "validate_ranges"
CONF_TRACK_CHANGES_ONLY = "track_changes_only"

# Retry and transmission configuration
CONF_MAX_RETRY_ATTEMPTS = "max_retry_attempts"
CONF_RETRY_BASE_DELAY = "retry_base_delay"
CONF_RETRY_MAX_DELAY = "retry_max_delay"
CONF_RETRY_QUEUE_SIZE = "retry_queue_size"
CONF_ENABLE_RETRY = "enable_retry"

# Performance tuning configuration
CONF_PERFORMANCE_PROFILE = "performance_profile"
CONF_MAX_CONCURRENT_REQUESTS = "max_concurrent_requests"
CONF_MEMORY_LIMIT_MB = "memory_limit_mb"
CONF_ENABLE_AGGREGATION = "enable_aggregation"
CONF_AGGREGATION_WINDOW = "aggregation_window"

# Configuration templates
CONF_APPLY_TEMPLATE = "apply_template"
CONF_ENTITY_CONFIGS = "entity_configs"

# Health monitoring
CONF_ENABLE_HEALTH_MONITORING = "enable_health_monitoring"
CONF_HEALTH_CHECK_INTERVAL = "health_check_interval"

# Default performance values
DEFAULT_PERFORMANCE_PROFILE = "balanced"
DEFAULT_MAX_CONCURRENT_REQUESTS = 2
DEFAULT_MEMORY_LIMIT_MB = 100
DEFAULT_ENABLE_AGGREGATION = False
DEFAULT_AGGREGATION_WINDOW = 300
DEFAULT_ENABLE_HEALTH_MONITORING = True
DEFAULT_HEALTH_CHECK_INTERVAL = 60

# Publishing options
CONF_PUBLISHING_STRATEGY = "publishing_strategy"
CONF_PUBLISHING_RULES = "publishing_rules"
CONF_AUTO_PUBLISH = "auto_publish"
CONF_DEFAULT_VISIBLE = "default_visible"
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
ENTRY_DATA_HISTORICAL_SYNC = "historical_sync"
ENTRY_DATA_CONFIG_MANAGER = "config_manager"
ENTRY_DATA_PERFORMANCE_MANAGER = "performance_manager"
ENTRY_DATA_HEALTH_MONITOR = "health_monitor"

# Service names
SERVICE_PUBLISH_ENTITY = "publish_entity"
SERVICE_PUBLISH_ENTITIES = "publish_entities"
SERVICE_PUBLISH_ALL_TRACKED = "publish_all_tracked"
SERVICE_UPDATE_ITEM_VISIBILITY = "update_item_visibility"
SERVICE_PUBLISH_DOMAIN = "publish_domain"
SERVICE_PUBLISH_BY_DEVICE_CLASS = "publish_by_device_class"
SERVICE_UNPUBLISH_ENTITY = "unpublish_entity"
SERVICE_SYNC_PUBLISHING = "sync_publishing"

# Service fields
ATTR_ENTITY_ID = "entity_id"
ATTR_ENTITY_IDS = "entity_ids"
ATTR_VISIBLE = "visible"
ATTR_LABELS = "labels"
ATTR_DOMAIN = "domain"
ATTR_DEVICE_CLASS = "device_class"
ATTR_DEVICE_CLASSES = "device_classes"
ATTR_STRATEGY = "strategy"
ATTR_FORCE = "force"

# Clarify API constants
CLARIFY_API_URL_PROD = "https://api.clarify.io/v1/"
CLARIFY_API_URL_DEV = "https://api.clarify.cloud/v1/"
CLARIFY_API_URL = CLARIFY_API_URL_DEV  # Default for backward compatibility

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

# ============================================================================
# Phase 7: Advanced Features
# ============================================================================

# Service names
SERVICE_SYNC_HISTORICAL = "sync_historical"
SERVICE_FLUSH_BUFFER = "flush_buffer"
SERVICE_APPLY_TEMPLATE = "apply_template"
SERVICE_SET_ENTITY_CONFIG = "set_entity_config"
SERVICE_SET_PERFORMANCE_PROFILE = "set_performance_profile"
SERVICE_GET_HEALTH_REPORT = "get_health_report"
SERVICE_RESET_STATISTICS = "reset_statistics"

# Data aggregation
DEFAULT_AGGREGATION_METHOD = "none"
DEFAULT_AGGREGATION_WINDOW = 300  # 5 minutes
DEFAULT_MIN_CHANGE_THRESHOLD = 0.01  # 1% change

# Available aggregation methods
AGGREGATION_METHODS = [
    "none",
    "average",
    "median",
    "min",
    "max",
    "sum",
    "first",
    "last",
    "count",
    "change_only",
]

# Configuration templates
AVAILABLE_TEMPLATES = [
    "energy_monitoring",
    "environmental_monitoring",
    "hvac_monitoring",
    "binary_sensor",
    "motion_analytics",
    "lighting_control",
    "comprehensive",
    "real_time_critical",
]

# Performance profiles
AVAILABLE_PROFILES = [
    "minimal",
    "balanced",
    "high_performance",
    "real_time",
]

# Historical sync defaults
DEFAULT_HISTORICAL_BATCH_SIZE = 1000
DEFAULT_HISTORICAL_BATCH_DELAY = 2.0  # seconds
MAX_HISTORICAL_BATCH_SIZE = 10000
MIN_HISTORICAL_BATCH_DELAY = 0.5

# Automation event types
EVENT_DATA_SYNCED = f"{DOMAIN}_data_synced"
EVENT_BUFFER_FLUSHED = f"{DOMAIN}_buffer_flushed"
EVENT_TRANSMISSION_SUCCESS = f"{DOMAIN}_transmission_success"
EVENT_TRANSMISSION_FAILED = f"{DOMAIN}_transmission_failed"
EVENT_HEALTH_STATUS_CHANGED = f"{DOMAIN}_health_status_changed"

# ============================================================================
# Phase 8: Security and Privacy
# ============================================================================

# Credential storage
CREDENTIAL_STORAGE_VERSION = 1
CREDENTIAL_STORAGE_KEY = "clarify_credentials"

# Token refresh settings
TOKEN_REFRESH_BUFFER_MINUTES = 5  # Refresh 5 minutes before expiration
TOKEN_CHECK_INTERVAL_SECONDS = 300  # Check tokens every 5 minutes
MAX_REFRESH_RETRIES = 3
REFRESH_RETRY_DELAY_SECONDS = 30

# Credential validation
MIN_CLIENT_ID_LENGTH = 10
MIN_CLIENT_SECRET_LENGTH = 20
VALIDATION_CACHE_TIMEOUT_MINUTES = 5

# Secure logging
MASK_CREDENTIAL_CHARS = 4  # Number of characters to show in masked strings

# Credential entry data keys
ENTRY_DATA_CREDENTIAL_MANAGER = "credential_manager"
ENTRY_DATA_TOKEN_MANAGER = "token_manager"
