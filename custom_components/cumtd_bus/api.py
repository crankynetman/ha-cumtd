"""CUMTD API client for Home Assistant."""

import asyncio
from datetime import datetime

import httpx
from pydantic import BaseModel, Field

# ===== Data Models =====


class Route(BaseModel):
    """Route information."""

    route_id: str
    route_short_name: str | None = None


class Departure(BaseModel):
    """Real-time departure information."""

    stop_id: str
    headsign: str
    route: Route
    trip: dict  # Contains trip_id, direction, trip_headsign
    expected: datetime
    expected_mins: int
    scheduled: datetime
    is_monitored: bool  # Has real-time GPS tracking

    @property
    def direction(self) -> str | None:
        """Get direction from trip data."""
        return self.trip.get("direction") if self.trip else None

    @property
    def trip_id(self) -> str | None:
        """Get trip_id from trip data."""
        return self.trip.get("trip_id") if self.trip else None


class Stop(BaseModel):
    """A bus stop location."""

    stop_id: str
    stop_name: str


class DeparturesResponse(BaseModel):
    """Response from get departures."""

    time: datetime
    departures: list[Departure] = Field(default_factory=list)


class StopsResponse(BaseModel):
    """Response from get stops."""

    time: datetime
    stops: list[Stop] = Field(default_factory=list)


class RoutesResponse(BaseModel):
    """Response from get routes by stop."""

    time: datetime
    routes: list[Route] = Field(default_factory=list)


# ===== Exceptions =====


class CUMTDAPIError(Exception):
    """Base exception for CUMTD API errors."""


class AuthenticationError(CUMTDAPIError):
    """Invalid API key."""


# ===== Client =====


class CUMTDClient:
    """CUMTD API client for departure tracking."""

    BASE_URL = "https://developer.cumtd.com/api/v2.2/json"

    def __init__(self, api_key: str) -> None:
        """
        Initialize CUMTD client.

        Args:
            api_key: CUMTD API key
        """
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is created (lazy initialization to avoid blocking).

        We use asyncio.to_thread() because httpx.AsyncClient.__init__() blocks
        the event loop during SSL certificate loading (causes HA warnings).
        """
        if self._client is None:
            self._client = await asyncio.to_thread(lambda: httpx.AsyncClient(timeout=10.0))
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()

    async def _request(self, method: str, params: dict) -> dict:
        """
        Make an API request.

        Args:
            method: API method name (e.g., 'getdeparturesbystop')
            params: Query parameters (no API key needed)

        Returns:
            Response data as dict

        Raises:
            CUMTDAPIError: On API errors
            AuthenticationError: If API key is invalid
        """
        url = f"{self.BASE_URL}/{method}"
        params["key"] = self.api_key

        client = await self._ensure_client()
        response = await client.get(url, params=params)

        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")

        data = response.json()

        if "status" in data and data["status"]["code"] != 200:
            raise CUMTDAPIError(f"API error {data['status']['code']}: {data['status']['msg']}")

        return data

    async def validate_api_key(self) -> bool:
        """
        Validate API key by making a test request.

        Returns:
            True if API key is valid

        Raises:
            AuthenticationError: If API key is invalid
        """
        try:
            await self._request("getstops", {})
            return True
        except AuthenticationError:
            raise
        except CUMTDAPIError:
            # Other API errors still mean the key is valid
            return True

    async def get_departures_by_stop(
        self,
        stop_id: str,
        route_id: str | None = None,
        count: int | None = None,
    ) -> DeparturesResponse:
        """Get departures at a stop with real-time predictions.

        This is the primary method for tracking when buses arrive.

        Args:
            stop_id: Stop identifier (e.g., 'SPFLDPINE')
            route_id: Optional route filter (e.g., '5' for Green)
            count: Optional max number of departures to return

        Returns:
            DeparturesResponse with list of upcoming departures"""
        params = {
            "stop_id": stop_id,
            "route_id": route_id,
            "count": count,
        }

        data = await self._request("getdeparturesbystop", params)

        return DeparturesResponse(
            time=data["time"],
            departures=[Departure(**d) for d in data.get("departures", [])],
        )

    async def get_stops_by_search(self, query: str) -> StopsResponse:
        """
        Search for stops by name.

        Args:
            query: Search query (e.g., 'Illinois terminal')

        Returns:
            StopsResponse with matching stops
        """
        data = await self._request("getstops", {})
        all_stops = [Stop(**s) for s in data.get("stops", [])]

        # Simple case-insensitive search
        query_lower = query.lower()
        matching_stops = [stop for stop in all_stops if query_lower in stop.stop_name.lower()]

        return StopsResponse(
            time=data["time"],
            stops=matching_stops,
        )

    async def get_routes_by_stop(self, stop_id: str) -> RoutesResponse:
        """Get all routes that service a stop (not just currently running)."""
        params = {"stop_id": stop_id}
        data = await self._request("getroutesbystop", params)

        routes = [Route(**r) for r in data.get("routes", [])]

        return RoutesResponse(
            time=data["time"],
            routes=routes,
        )


__all__ = [
    "AuthenticationError",
    "CUMTDAPIError",
    "CUMTDClient",
    "Departure",
    "DeparturesResponse",
    "Stop",
    "StopsResponse",
]
