"""Tests for CUMTD Bus sensor."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from custom_components.cumtd_bus.api import Departure
from custom_components.cumtd_bus.sensor import CUMTDNextBusSensor


@pytest.fixture
def mock_coordinator():
    """Mock coordinator."""
    coordinator = MagicMock()
    coordinator.stop_id = "TESTIUTERM"
    coordinator.stop_name = "Test & Lynn"
    coordinator.data = None
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
def mock_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    return entry


@pytest.fixture
def stop_config():
    """Mock stop configuration."""
    return {
        "stop_id": "TESTIUTERM",
        "stop_name": "Test & Lynn",
        "route_id": None,
        "direction_filter": None,
    }


@pytest.fixture
def sensor(mock_coordinator, mock_entry, stop_config):
    """Sensor with mocked coordinator."""
    return CUMTDNextBusSensor(mock_coordinator, mock_entry, stop_config, custom_name=None)


def test_sensor_initialization(sensor, mock_coordinator, mock_entry) -> None:
    """Sensor initializes with correct name/id."""
    # With no custom_name, uses stop_name
    assert sensor._attr_name == "Test & Lynn Next Bus"
    assert sensor._attr_unique_id == f"{mock_entry.entry_id}_testiuterm_all_all"


def test_sensor_no_data(sensor, mock_coordinator) -> None:
    """Sensor with no data returns None."""
    mock_coordinator.data = None

    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None
    # Sensor is available even with no data if coordinator update succeeded
    assert sensor.available is True


def test_sensor_with_data(sensor, mock_coordinator) -> None:
    """Sensor with departure data populates value and attributes."""
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5", route_short_name="5"),
        trip={"trip_id": "trip_789", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=8,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_coordinator.data = departure

    # Check value
    assert sensor.native_value == 8
    assert sensor.native_unit_of_measurement == "min"

    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["headsign"] == "5E Green"
    assert attrs["direction"] == "Eastbound"
    assert attrs["route"] == "5"
    assert attrs["is_real_time"] is True
    assert attrs["stop_id"] == "TESTIUTERM"
    assert attrs["stop_name"] == "Test & Lynn"
    assert attrs["trip_id"] == "trip_789"
    assert "scheduled" in attrs
    assert "expected" in attrs


def test_sensor_scheduled_only(sensor, mock_coordinator) -> None:
    """Scheduled (non-real-time) departures work."""
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="130 Carle",
        route=Route(route_id="130", route_short_name="130"),
        trip={"trip_id": "trip_999", "direction": "Westbound"},
        expected=datetime(2026, 1, 17, 15, 00),
        expected_mins=15,
        scheduled=datetime(2026, 1, 17, 15, 00),
        is_monitored=False,  # Not real-time
        is_scheduled=True,
    )
    mock_coordinator.data = departure

    assert sensor.native_value == 15

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["headsign"] == "130 Carle"
    assert attrs["is_real_time"] is False


def test_sensor_handles_coordinator_data_changes(mock_coordinator, mock_entry, stop_config) -> None:
    """Sensor updates when coordinator data changes."""
    from custom_components.cumtd_bus.api import Route

    sensor = CUMTDNextBusSensor(mock_coordinator, mock_entry, stop_config, None)

    # Initially no data
    mock_coordinator.data = None
    assert sensor.native_value is None

    # Data arrives
    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5", route_short_name="5"),
        trip={"trip_id": "trip_1", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_coordinator.data = departure
    assert sensor.native_value == 5

    # Data updates
    departure_2 = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5", route_short_name="5"),
        trip={"trip_id": "trip_1", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 32),
        expected_mins=7,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_coordinator.data = departure_2
    assert sensor.native_value == 7


def test_sensor_custom_name(mock_coordinator, mock_entry, stop_config) -> None:
    """Custom name overrides stop name."""
    sensor = CUMTDNextBusSensor(
        mock_coordinator, mock_entry, stop_config, custom_name="My Custom Stop"
    )

    assert sensor._attr_name == "My Custom Stop Next Bus"
    # Unique ID stays the same regardless of custom name
    assert sensor._attr_unique_id == f"{mock_entry.entry_id}_testiuterm_all_all"


def test_sensor_unavailable_after_update_failure(sensor, mock_coordinator) -> None:
    """Sensor unavailable when coordinator update fails."""
    mock_coordinator.last_update_success = False
    mock_coordinator.data = None

    assert sensor.available is False
    assert sensor.native_value is None


def test_sensor_available_with_data(sensor, mock_coordinator) -> None:
    """Sensor available when coordinator updated successfully."""
    from custom_components.cumtd_bus.api import Route

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="5E Green",
        route=Route(route_id="5", route_short_name="5"),
        trip={"trip_id": "trip_123", "direction": "Eastbound"},
        expected=datetime(2026, 1, 17, 14, 30),
        expected_mins=5,
        scheduled=datetime(2026, 1, 17, 14, 28),
        is_monitored=True,
        is_scheduled=True,
    )
    mock_coordinator.data = departure
    mock_coordinator.last_update_success = True

    assert sensor.available is True
    assert sensor.native_value == 5


def test_sensor_unique_id_sanitization(mock_coordinator, mock_entry) -> None:
    """Unique ID sanitizes colons and spaces."""
    # IU stops use format "IU:1", "IU:2", etc.
    stop_config = {
        "stop_id": "IU:1",
        "stop_name": "Illini Union",
        "route_id": "50E",  # Route with letter
        "direction_filter": "East Bound",  # Direction with space
    }
    sensor = CUMTDNextBusSensor(mock_coordinator, mock_entry, stop_config, None)

    # Should sanitize: colon -> underscore, spaces -> underscores, lowercase
    assert sensor._attr_unique_id == f"{mock_entry.entry_id}_iu_1_50e_east_bound"
    # Ensure no colons or uppercase in unique_id
    assert ":" not in sensor._attr_unique_id
    assert sensor._attr_unique_id == sensor._attr_unique_id.lower()


def test_sensor_attributes_reflect_coordinator_data(
    mock_coordinator, mock_entry, stop_config
) -> None:
    """Sensor attributes update when coordinator provides new departure data."""
    from custom_components.cumtd_bus.api import Route

    sensor = CUMTDNextBusSensor(mock_coordinator, mock_entry, stop_config, None)

    departure = Departure(
        stop_id="TESTIUTERM",
        headsign="22 Illini",
        route=Route(route_id="22", route_short_name="22I"),
        trip={"trip_id": "xyz", "direction": "Southbound"},
        expected=datetime(2026, 1, 17, 15, 45),
        expected_mins=12,
        scheduled=datetime(2026, 1, 17, 15, 40),
        is_monitored=False,
        is_scheduled=True,
    )
    mock_coordinator.data = departure

    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["headsign"] == "22 Illini"
    assert attrs["direction"] == "Southbound"
    assert attrs["route"] == "22I"
    assert attrs["is_real_time"] is False
    assert attrs["trip_id"] == "xyz"
