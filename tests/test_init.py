"""Tests for CUMTD Bus integration setup and teardown."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.cumtd_bus import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.cumtd_bus.const import (
    CONF_API_KEY,
    CONF_DIRECTION_FILTER,
    CONF_ROUTE_ID,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_STOPS,
    DOMAIN,
)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Config entry fixture."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {
        CONF_STOPS: [
            {
                CONF_STOP_ID: "STOP1",
                CONF_STOP_NAME: "Test Stop 1",
                CONF_ROUTE_ID: None,
                CONF_DIRECTION_FILTER: None,
            },
            {
                CONF_STOP_ID: "STOP2",
                CONF_STOP_NAME: "Test Stop 2",
                CONF_ROUTE_ID: "5",
                CONF_DIRECTION_FILTER: "North",
            },
        ]
    }
    entry.async_on_unload = MagicMock(return_value=None)
    entry.add_update_listener = MagicMock()
    return entry


async def test_setup_entry_creates_coordinators(mock_hass, mock_config_entry) -> None:
    """Setup creates one coordinator per stop."""
    with (
        patch("custom_components.cumtd_bus.CUMTDClient") as mock_client_class,
        patch("custom_components.cumtd_bus.CUMTDBusCoordinator") as mock_coordinator_class,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result
        # Should create 2 coordinators (one per stop)
        assert mock_coordinator_class.call_count == 2
        # Should store client and coordinators
        assert DOMAIN in mock_hass.data
        assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
        assert "client" in mock_hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "coordinators" in mock_hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_unload_entry_closes_client(mock_hass, mock_config_entry) -> None:
    """Unload closes the API client."""
    # Set up some data
    mock_client = AsyncMock()
    mock_hass.data[DOMAIN][mock_config_entry.entry_id] = {
        "client": mock_client,
        "coordinators": {},
    }

    result = await async_unload_entry(mock_hass, mock_config_entry)

    assert result
    mock_client.close.assert_awaited_once()
    # Data should be removed
    assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]


async def test_reload_entry_cleans_up_orphaned_entities(mock_hass, mock_config_entry) -> None:
    """Reload removes entities for deleted stops."""
    # Mock entity registry
    mock_entity_registry = MagicMock()

    # Create mock entity entries
    entity_stop1 = MagicMock()
    entity_stop1.unique_id = "test_entry_123_STOP1_all_all"
    entity_stop1.entity_id = "sensor.stop1_next_bus"

    entity_stop2 = MagicMock()
    entity_stop2.unique_id = "test_entry_123_STOP2_5_North"
    entity_stop2.entity_id = "sensor.stop2_next_bus"

    # This one is orphaned (STOP3 not in config)
    entity_orphan = MagicMock()
    entity_orphan.unique_id = "test_entry_123_STOP3_all_all"
    entity_orphan.entity_id = "sensor.stop3_next_bus"

    mock_entity_registry.async_entries_for_config_entry.return_value = [
        entity_stop1,
        entity_stop2,
        entity_orphan,
    ]

    with (
        patch("custom_components.cumtd_bus.er.async_get") as mock_async_get,
        patch(
            "custom_components.cumtd_bus.er.async_entries_for_config_entry"
        ) as mock_async_entries,
    ):
        mock_async_get.return_value = mock_entity_registry
        mock_async_entries.return_value = [
            entity_stop1,
            entity_stop2,
            entity_orphan,
        ]
        await async_reload_entry(mock_hass, mock_config_entry)

        # Should remove the orphaned entity
        mock_entity_registry.async_remove.assert_called_once_with("sensor.stop3_next_bus")
        # Should reload the entry
        mock_hass.config_entries.async_reload.assert_awaited_once_with("test_entry_123")


async def test_reload_entry_keeps_valid_entities(mock_hass, mock_config_entry) -> None:
    """Reload keeps entities for configured stops."""
    mock_entity_registry = MagicMock()

    # Only entities that match current config
    entity_stop1 = MagicMock()
    entity_stop1.unique_id = "test_entry_123_STOP1_all_all"
    entity_stop1.entity_id = "sensor.stop1_next_bus"

    entity_stop2 = MagicMock()
    entity_stop2.unique_id = "test_entry_123_STOP2_5_North"
    entity_stop2.entity_id = "sensor.stop2_next_bus"

    mock_entity_registry.async_entries_for_config_entry.return_value = [
        entity_stop1,
        entity_stop2,
    ]

    with (
        patch("custom_components.cumtd_bus.er.async_get") as mock_async_get,
        patch(
            "custom_components.cumtd_bus.er.async_entries_for_config_entry"
        ) as mock_async_entries,
    ):
        mock_async_get.return_value = mock_entity_registry
        mock_async_entries.return_value = [
            entity_stop1,
            entity_stop2,
        ]
        await async_reload_entry(mock_hass, mock_config_entry)

        # Should NOT remove any entities
        mock_entity_registry.async_remove.assert_not_called()


async def test_cleanup_removes_multiple_orphans(mock_hass, mock_config_entry) -> None:
    """Cleanup removes multiple orphaned entities."""
    mock_entity_registry = MagicMock()

    # Valid entity
    entity_valid = MagicMock()
    entity_valid.unique_id = "test_entry_123_STOP1_all_all"
    entity_valid.entity_id = "sensor.stop1_next_bus"

    # Multiple orphans
    orphan1 = MagicMock()
    orphan1.unique_id = "test_entry_123_OLDSTOP_all_all"
    orphan1.entity_id = "sensor.oldstop_next_bus"

    orphan2 = MagicMock()
    orphan2.unique_id = "test_entry_123_STOP2_10_South"  # Different route/direction
    orphan2.entity_id = "sensor.stop2_route10_next_bus"

    mock_entity_registry.async_entries_for_config_entry.return_value = [
        entity_valid,
        orphan1,
        orphan2,
    ]

    with (
        patch("custom_components.cumtd_bus.er.async_get") as mock_async_get,
        patch(
            "custom_components.cumtd_bus.er.async_entries_for_config_entry"
        ) as mock_async_entries,
    ):
        mock_async_get.return_value = mock_entity_registry
        mock_async_entries.return_value = [
            entity_valid,
            orphan1,
            orphan2,
        ]
        await async_reload_entry(mock_hass, mock_config_entry)

        # Should remove both orphans
        assert mock_entity_registry.async_remove.call_count == 2
        calls = [call[0][0] for call in mock_entity_registry.async_remove.call_args_list]
        assert "sensor.oldstop_next_bus" in calls
        assert "sensor.stop2_route10_next_bus" in calls


async def test_cleanup_with_no_stops_removes_all(mock_hass, mock_config_entry) -> None:
    """Cleanup removes all entities when no stops configured."""
    # Empty stops list
    mock_config_entry.options = {CONF_STOPS: []}

    mock_entity_registry = MagicMock()

    entity1 = MagicMock()
    entity1.unique_id = "test_entry_123_STOP1_all_all"
    entity1.entity_id = "sensor.stop1_next_bus"

    entity2 = MagicMock()
    entity2.unique_id = "test_entry_123_STOP2_5_North"
    entity2.entity_id = "sensor.stop2_next_bus"

    mock_entity_registry.async_entries_for_config_entry.return_value = [
        entity1,
        entity2,
    ]

    with (
        patch("custom_components.cumtd_bus.er.async_get") as mock_async_get,
        patch(
            "custom_components.cumtd_bus.er.async_entries_for_config_entry"
        ) as mock_async_entries,
    ):
        mock_async_get.return_value = mock_entity_registry
        mock_async_entries.return_value = [
            entity1,
            entity2,
        ]
        await async_reload_entry(mock_hass, mock_config_entry)

        # Should remove all entities
        assert mock_entity_registry.async_remove.call_count == 2
