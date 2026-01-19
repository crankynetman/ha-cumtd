"""Data update coordinator for CUMTD Bus."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CUMTDAPIError, CUMTDClient, Departure
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CUMTDBusCoordinator(DataUpdateCoordinator[Departure | None]):
    """Fetch bus departures from CUMTD API in background."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: CUMTDClient,
        stop_id: str,
        stop_name: str,
        route_id: str | None = None,
        direction_filter: str | None = None,
    ) -> None:
        """Initialize coordinator with stop and optional filters."""
        self.client = client
        self.stop_id = stop_id
        self.stop_name = stop_name
        self.route_id = route_id
        self.direction_filter = direction_filter

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{stop_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> Departure | None:
        """Fetch next departure from API, applying route/direction filters."""
        try:
            _LOGGER.debug(
                "Fetching departures for stop %s (route=%s, direction=%s)",
                self.stop_id,
                self.route_id or "all",
                self.direction_filter or "all",
            )

            response = await self.client.get_departures_by_stop(
                stop_id=self.stop_id,
                route_id=self.route_id,
                count=5,
            )

            if not response.departures:
                _LOGGER.debug("No departures found for stop %s", self.stop_id)
                return None

            # Direction filtering must be done client-side - CUMTD API doesn't support
            # direction parameter, only route_id (and even that's unreliable)
            departures = response.departures
            if self.direction_filter:
                departures = [
                    d
                    for d in departures
                    if d.direction and self.direction_filter.lower() == d.direction.lower()
                ]

            if not departures:
                _LOGGER.debug("No departures match direction filter: %s", self.direction_filter)
                return None

            next_departure = departures[0]

            _LOGGER.debug(
                "Next departure: %s in %d minutes",
                next_departure.headsign,
                next_departure.expected_mins,
            )

            return next_departure

        except CUMTDAPIError as err:
            raise UpdateFailed(f"Error fetching bus data: {err}") from err
