"""Constants for the CUMTD Bus Alerts integration."""

# Integration domain
DOMAIN = "cumtd_bus"

# Coordinator update interval (how often to poll the API)
DEFAULT_SCAN_INTERVAL = 15  # seconds

# Config entry data keys (stored in entry.data)
CONF_API_KEY = "api_key"

# Options keys (stored in entry.options)
CONF_STOPS = "stops"

# Stop configuration keys (within each stop dict)
CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_ROUTE_ID = "route_id"  # Optional filter
CONF_DIRECTION_FILTER = "direction_filter"  # Optional filter
CONF_CUSTOM_NAME = "custom_name"  # Optional user label
