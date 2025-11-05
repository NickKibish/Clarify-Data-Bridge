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
DEFAULT_NAME = "Clarify Data Bridge"

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"

# Entry data keys
ENTRY_DATA_CLIENT = "client"
ENTRY_DATA_COORDINATOR = "coordinator"

# Clarify API constants
CLARIFY_API_URL = "https://api.clarify.io/v1"
