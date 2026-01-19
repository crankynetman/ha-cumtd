"""Sensor for CUMTD Bus."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CUSTOM_NAME, CONF_STOPS, DOMAIN
from .coordinator import CUMTDBusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry - one per stop."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    stops = entry.options.get(CONF_STOPS, [])

    sensors = []
    for idx, coordinator in coordinators.items():
        stop_config = stops[idx]
        custom_name = stop_config.get(CONF_CUSTOM_NAME)
        sensors.append(
            CUMTDNextBusSensor(
                coordinator,
                entry,
                stop_config,
                custom_name,
            )
        )

    async_add_entities(sensors)


class CUMTDNextBusSensor(CoordinatorEntity[CUMTDBusCoordinator], SensorEntity):
    """Sensor showing minutes until next bus arrival."""

    def __init__(
        self,
        coordinator: CUMTDBusCoordinator,
        entry: ConfigEntry,
        stop_config: dict,
        custom_name: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        base_name = (
            custom_name or coordinator.stop_name or stop_config.get("stop_name") or "Bus Stop"
        )

        filter_parts = []
        if stop_config.get("route_id"):
            filter_parts.append(f"Route {stop_config['route_id']}")
        if stop_config.get("direction_filter"):
            filter_parts.append(stop_config["direction_filter"])

        filter_str = f" ({', '.join(filter_parts)})" if filter_parts else ""
        self._attr_name = f"{base_name}{filter_str} Next Bus"

        # Unique ID must include stop+route+direction to prevent collisions when
        # multiple sensors track the same stop with different filters
        stop_id = stop_config["stop_id"]
        route_id = stop_config.get("route_id") or "all"
        direction = stop_config.get("direction_filter") or "all"

        safe_stop = stop_id.replace(":", "_").replace(" ", "_").lower()
        safe_route = route_id.replace(" ", "_").lower()
        safe_direction = direction.replace(" ", "_").lower()

        self._attr_unique_id = f"{entry.entry_id}_{safe_stop}_{safe_route}_{safe_direction}"
        self._attr_icon = "mdi:bus"

    @property
    def native_value(self) -> int | None:
        """Return minutes until next bus arrival."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.expected_mins

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def native_unit_of_measurement(self) -> str:
        return "min"

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return None

        departure = self.coordinator.data
        return {
            "headsign": departure.headsign,
            "direction": departure.direction,
            "route": departure.route.route_short_name,
            "scheduled": departure.scheduled.isoformat(),
            "expected": departure.expected.isoformat(),
            "is_real_time": departure.is_monitored,
            "stop_id": departure.stop_id,
            "stop_name": self.coordinator.stop_name,
            "trip_id": departure.trip_id,
        }
