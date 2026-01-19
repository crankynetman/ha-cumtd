"""Tests for CUMTD Bus config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.cumtd_bus.api import AuthenticationError, CUMTDAPIError
from custom_components.cumtd_bus.config_flow import (
    CUMTDBusConfigFlow,
    CUMTDBusOptionsFlow,
)
from custom_components.cumtd_bus.const import (
    CONF_API_KEY,
    CONF_CUSTOM_NAME,
    CONF_DIRECTION_FILTER,
    CONF_ROUTE_ID,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_STOPS,
)
from homeassistant import config_entries


@pytest.fixture
def mock_client():
    """Mock CUMTDClient."""
    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


async def test_user_form_shows() -> None:
    """User form shown initially."""
    flow = CUMTDBusConfigFlow()
    flow.hass = None  # Not needed for form display

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert CONF_API_KEY in result["data_schema"].schema


async def test_valid_api_key_creates_entry(mock_client) -> None:
    """Valid API key creates entry."""
    mock_client.validate_api_key.return_value = True

    flow = CUMTDBusConfigFlow()
    flow.hass = AsyncMock()

    result = await flow.async_step_user(user_input={CONF_API_KEY: "test_valid_key"})

    # Hub pattern: creates entry immediately, stops managed via options
    assert result["type"] == "create_entry"
    assert result["title"] == "CUMTD Bus"
    assert result["data"][CONF_API_KEY] == "test_valid_key"
    # Verify empty stops list in options
    from custom_components.cumtd_bus.const import CONF_STOPS

    assert result["options"][CONF_STOPS] == []


async def test_authentication_error_shows_error(mock_client) -> None:
    """Authentication errors handled."""
    mock_client.validate_api_key.side_effect = AuthenticationError("Invalid key")

    flow = CUMTDBusConfigFlow()
    flow.hass = AsyncMock()

    result = await flow.async_step_user(user_input={CONF_API_KEY: "bad_key"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.close.assert_awaited_once()


async def test_api_error_shows_error(mock_client) -> None:
    """API errors handled."""
    mock_client.validate_api_key.side_effect = CUMTDAPIError("Connection failed")

    flow = CUMTDBusConfigFlow()
    flow.hass = AsyncMock()

    result = await flow.async_step_user(user_input={CONF_API_KEY: "test_key"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.close.assert_awaited_once()


async def test_unknown_error_shows_error(mock_client) -> None:
    """Unknown errors handled."""
    mock_client.validate_api_key.side_effect = Exception("Something broke")

    flow = CUMTDBusConfigFlow()
    flow.hass = AsyncMock()

    result = await flow.async_step_user(user_input={CONF_API_KEY: "test_key"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    mock_client.close.assert_awaited_once()


# Options Flow Tests


@pytest.fixture
def mock_config_entry():
    """Options flow config entry."""
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {CONF_STOPS: []}
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = AsyncMock()
    hass.config_entries = MagicMock()
    return hass


async def test_options_init_shows_menu(mock_config_entry) -> None:
    """Options flow shows menu."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert "edit_api_key" in result["menu_options"]
    assert "add_stop" in result["menu_options"]


async def test_options_add_stop_starts_search(mock_config_entry) -> None:
    """Add stop redirects to search."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    result = await flow.async_step_add_stop(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "stop_search"


async def test_stop_search_empty_query_shows_error(mock_config_entry) -> None:
    """Empty query shows error."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient"):
        result = await flow.async_step_stop_search(user_input={"search_query": "  "})

    assert result["type"] == "form"
    assert result["errors"] == {"search_query": "empty_search"}


async def test_stop_search_finds_stops(mock_config_entry) -> None:
    """Test stop search returns stops."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client

        # Mock API response
        stop1 = MagicMock()
        stop1.stop_id = "STOP1"
        stop1.stop_name = "Test Stop 1"

        stop2 = MagicMock()
        stop2.stop_id = "STOP2"
        stop2.stop_name = "Test Stop 2"

        response = MagicMock()
        response.stops = [stop1, stop2]
        client.get_stops_by_search.return_value = response

        result = await flow.async_step_stop_search(user_input={"search_query": "test"})

        assert result["type"] == "form"
        assert result["step_id"] == "stop_search"
        assert "stop_selection" in result["data_schema"].schema
        client.close.assert_awaited_once()


async def test_stop_search_no_results_shows_error(mock_config_entry) -> None:
    """Test stop search with no results shows error."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client

        response = MagicMock()
        response.stops = []
        client.get_stops_by_search.return_value = response

        result = await flow.async_step_stop_search(user_input={"search_query": "nonexistent"})

        assert result["type"] == "form"
        assert result["errors"] == {"search_query": "no_stops_found"}


async def test_stop_selection_proceeds_to_configure(mock_config_entry) -> None:
    """Test selecting a stop proceeds to configure."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow._stop_search_results = {"STOP1": "Test Stop"}

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client

        # Mock routes response
        route = MagicMock()
        route.route_short_name = "5"
        routes_response = MagicMock()
        routes_response.routes = [route]
        client.get_routes_by_stop.return_value = routes_response

        # Mock departures response (can fail)
        client.get_departures_by_stop.side_effect = CUMTDAPIError("500")

        result = await flow.async_step_stop_search(user_input={"stop_selection": "STOP1"})

        assert result["type"] == "form"
        assert result["step_id"] == "stop_configure"
        assert flow._stop_data[CONF_STOP_ID] == "STOP1"
        assert flow._stop_data[CONF_STOP_NAME] == "Test Stop"


async def test_stop_configure_saves_stop(mock_config_entry) -> None:
    """Test stop configure saves the stop."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow._stop_data = {
        CONF_STOP_ID: "STOP1",
        CONF_STOP_NAME: "Test Stop",
    }

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client

        route = MagicMock()
        route.route_short_name = "5"
        routes_response = MagicMock()
        routes_response.routes = [route]
        client.get_routes_by_stop.return_value = routes_response
        client.get_departures_by_stop.side_effect = CUMTDAPIError("500")

        result = await flow.async_step_stop_configure(
            user_input={
                "route_id": "5",
                "direction_filter": "North",
                "custom_name": "My Stop",
            }
        )

        assert result["type"] == "create_entry"
        assert len(result["data"][CONF_STOPS]) == 1
        stop = result["data"][CONF_STOPS][0]
        assert stop[CONF_STOP_ID] == "STOP1"
        assert stop[CONF_ROUTE_ID] == "5"
        assert stop[CONF_DIRECTION_FILTER] == "North"
        assert stop[CONF_CUSTOM_NAME] == "My Stop"


async def test_manage_stops_shows_stops(mock_config_entry) -> None:
    """Manage stops displays configured stops."""
    mock_config_entry.options = {
        CONF_STOPS: [
            {CONF_STOP_ID: "STOP1", CONF_STOP_NAME: "Test Stop 1"},
            {CONF_STOP_ID: "STOP2", CONF_STOP_NAME: "Test Stop 2"},
        ]
    }

    flow = CUMTDBusOptionsFlow(mock_config_entry)
    result = await flow.async_step_manage_stops(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "manage_stops"
    assert "stop_index" in result["data_schema"].schema


async def test_manage_stops_empty_redirects(mock_config_entry) -> None:
    """No stops redirects to init."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)

    result = await flow.async_step_manage_stops(user_input=None)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"


async def test_stop_action_shows_edit_remove(mock_config_entry) -> None:
    """Stop action shows edit/remove options."""
    mock_config_entry.options = {CONF_STOPS: [{CONF_STOP_ID: "STOP1", CONF_STOP_NAME: "Test Stop"}]}

    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow._edit_index = 0

    result = await flow.async_step_stop_action(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "stop_action"
    assert "action" in result["data_schema"].schema


async def test_stop_action_edit_proceeds_to_configure(mock_config_entry) -> None:
    """Test stop action edit proceeds to configure step."""
    mock_config_entry.options = {
        CONF_STOPS: [
            {
                CONF_STOP_ID: "STOP1",
                CONF_STOP_NAME: "Test Stop",
                CONF_ROUTE_ID: "5",
            }
        ]
    }

    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow._edit_index = 0

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client

        route = MagicMock()
        route.route_short_name = "5"
        routes_response = MagicMock()
        routes_response.routes = [route]
        client.get_routes_by_stop.return_value = routes_response
        client.get_departures_by_stop.side_effect = CUMTDAPIError("500")

        result = await flow.async_step_stop_action(user_input={"action": "edit"})

        assert result["type"] == "form"
        assert result["step_id"] == "stop_configure"
        assert flow._stop_data[CONF_STOP_ID] == "STOP1"


async def test_stop_action_remove_deletes_stop(mock_config_entry) -> None:
    """Remove deletes the stop."""
    mock_config_entry.options = {
        CONF_STOPS: [
            {CONF_STOP_ID: "STOP1", CONF_STOP_NAME: "Test Stop 1"},
            {CONF_STOP_ID: "STOP2", CONF_STOP_NAME: "Test Stop 2"},
        ]
    }

    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow._edit_index = 0

    result = await flow.async_step_stop_action(user_input={"action": "remove"})

    assert result["type"] == "create_entry"
    assert len(result["data"][CONF_STOPS]) == 1
    assert result["data"][CONF_STOPS][0][CONF_STOP_ID] == "STOP2"


async def test_edit_api_key_updates_entry(mock_config_entry, mock_hass) -> None:
    """Editing API key updates entry."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow.hass = mock_hass

    # Make async_reload actually awaitable
    mock_hass.config_entries.async_reload = AsyncMock()

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        client.validate_api_key.return_value = True

        result = await flow.async_step_edit_api_key(user_input={CONF_API_KEY: "new_key"})

        assert result["type"] == "create_entry"
        mock_hass.config_entries.async_update_entry.assert_called_once()
        mock_hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")


async def test_edit_api_key_invalid_shows_error(mock_config_entry, mock_hass) -> None:
    """Test editing API key with invalid key shows error."""
    flow = CUMTDBusOptionsFlow(mock_config_entry)
    flow.hass = mock_hass

    with patch("custom_components.cumtd_bus.config_flow.CUMTDClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        client.validate_api_key.side_effect = AuthenticationError("Invalid")

        result = await flow.async_step_edit_api_key(user_input={CONF_API_KEY: "bad_key"})

        assert result["type"] == "form"
        assert result["errors"] == {"base": "invalid_auth"}
