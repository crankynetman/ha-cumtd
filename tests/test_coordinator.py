"""Tests for CUMTD Bus coordinator logic."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.cumtd_bus.api import CUMTDAPIError, Departure, DeparturesResponse
from custom_components.cumtd_bus.coordinator import CUMTDBusCoordinator


@pytest.fixture
def mock_client():
    """Mock CUMTD client."""
    return AsyncMock()


async def test_coordinator_fetch_logic_success(mock_client) -> None:
    """Successful data fetch."""
    # Mock API response
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_123", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure],
    )

    # Create coordinator with minimal setup
    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = "5"
        coordinator.direction_filter = None

        # Test the fetch logic
        result = await coordinator._async_update_data()

        assert result == departure
        assert result.headsign == "5E Green"
        assert result.expected_mins == 5


async def test_coordinator_no_departures_logic(mock_client) -> None:
    """Handling of no departures."""
    # Mock empty response
    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.route_id = "5"
        coordinator.direction_filter = None

        result = await coordinator._async_update_data()

        assert result is None


async def test_coordinator_api_error_logic(mock_client) -> None:
    """API errors raise UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    # Mock API error
    mock_client.get_departures_by_stop.side_effect = CUMTDAPIError("Connection failed")

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.route_id = "5"
        coordinator.direction_filter = None

        with pytest.raises(UpdateFailed, match="Error fetching bus data"):
            await coordinator._async_update_data()


async def test_coordinator_without_route_filter_logic(mock_client) -> None:
    """Coordinator without route filtering."""
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="50E Green",
        route=Route(route_id="50"),
        trip={"trip_id": "trip_456", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=10,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = None  # No filter
        coordinator.direction_filter = None

        result = await coordinator._async_update_data()

        assert result == departure
        mock_client.get_departures_by_stop.assert_awaited_once_with(
            stop_id="TESTIUTERM",
            route_id=None,
            count=5,
        )


async def test_coordinator_direction_filter_match(mock_client) -> None:
    """Test coordinator with direction filter that matches."""
    from custom_components.cumtd_bus.api import Route

    departure_east = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_123", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    departure_west = Departure(
        stop_id="TESTIUTERM",
        headsign="5W Teal",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_456", "direction": "Westbound"},
        expected=datetime(2026, 1, 17, 14, 35),
        expected_mins=10,
        scheduled=datetime(2026, 1, 17, 14, 33),
        is_monitored=True,
        is_scheduled=True,
    )

    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure_east, departure_west],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = "5"
        coordinator.direction_filter = "Eastbound"

        result = await coordinator._async_update_data()

        # Should return the Eastbound departure
        assert result == departure_east
        assert result.headsign == "5E Green"


async def test_coordinator_direction_filter_no_match(mock_client) -> None:
    """Test coordinator with direction filter that doesn't match."""
    from custom_components.cumtd_bus.api import Route

    departure_west = Departure(
        stop_id="TESTIUTERM",
        headsign="5W Teal",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_456", "direction": "Westbound"},
        expected=datetime(2026, 1, 17, 14, 35),
        expected_mins=10,
        scheduled=datetime(2026, 1, 17, 14, 33),
        is_monitored=True,
        is_scheduled=True,
    )

    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure_west],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = "5"
        coordinator.direction_filter = "Eastbound"  # Only looking for Eastbound

        result = await coordinator._async_update_data()

        # Should return None because no Eastbound departures
        assert result is None


async def test_coordinator_direction_filter_case_insensitive(mock_client) -> None:
    """Test coordinator direction filter is case-insensitive."""
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_123", "direction": "EASTBOUND"},  # Uppercase in API
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )

    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = "5"
        coordinator.direction_filter = "eastbound"  # Lowercase in config

        result = await coordinator._async_update_data()

        # Should match case-insensitively
        assert result == departure


async def test_coordinator_combined_filters(mock_client) -> None:
    """Test coordinator with both route and direction filters."""
    from custom_components.cumtd_bus.api import Route

    # Multiple routes and directions
    departure_5_east = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_5e", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    Departure(
        stop_id="TESTIUTERM",
        headsign="50E Green",
        route=Route(route_id="50"),
        trip={"trip_id": "trip_50e", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 32),
        expected_mins=7,
        scheduled=datetime(2026, 1, 17, 14, 30),
        is_monitored=True,
        is_scheduled=True,
    )
    departure_5_west = Departure(
        stop_id="TESTIUTERM",
        headsign="5W Teal",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_5w", "direction": "Westbound"},
        expected=datetime(2026, 1, 17, 14, 35),
        expected_mins=10,
        scheduled=datetime(2026, 1, 17, 14, 33),
        is_monitored=True,
        is_scheduled=True,
    )

    # Route filter handled by API, so we only get route 5
    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure_5_east, departure_5_west],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = "5"  # Route filter (API-side)
        coordinator.direction_filter = "Eastbound"  # Direction filter (client-side)

        result = await coordinator._async_update_data()

        # Should return only the 5 Eastbound
        assert result == departure_5_east
        assert result.headsign == "5E Green"


async def test_coordinator_direction_none_in_trip(mock_client) -> None:
    """Test coordinator handles missing direction field gracefully."""
    from custom_components.cumtd_bus.api import Route

    departure_with_direction = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5"),
        trip={"trip_id": "trip_123", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    departure_no_direction = Departure(
        stop_id="TESTIUTERM",
        headsign="10 Illini",
        route=Route(route_id="10"),
        trip={"trip_id": "trip_456"},  # Missing direction
        expected=datetime(2026, 1, 17, 14, 32),
        expected_mins=7,
        scheduled=datetime(2026, 1, 17, 14, 30),
        is_monitored=True,
        is_scheduled=True,
    )

    mock_client.get_departures_by_stop.return_value = DeparturesResponse(
        time=datetime.now(),
        departures=[departure_no_direction, departure_with_direction],
    )

    with patch(
        "custom_components.cumtd_bus.coordinator.DataUpdateCoordinator.__init__", return_value=None
    ):
        coordinator = CUMTDBusCoordinator.__new__(CUMTDBusCoordinator)
        coordinator.client = mock_client
        coordinator.stop_id = "TESTIUTERM"
        coordinator.stop_name = "Test Illinois Terminal"
        coordinator.route_id = None
        coordinator.direction_filter = "Eastbound"

        result = await coordinator._async_update_data()

        # Should skip departure without direction and return the one with direction
        assert result == departure_with_direction
        assert result.headsign == "5E Green"
