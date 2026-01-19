"""CUMTD Bus Alerts integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import CUMTDClient
from .const import (
    CONF_API_KEY,
    CONF_DIRECTION_FILTER,
    CONF_ROUTE_ID,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_STOPS,
    DOMAIN,
)
from .coordinator import CUMTDBusCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CUMTD Bus from a config entry (hub pattern: one client, N coordinators)."""
    api_key = entry.data[CONF_API_KEY]

    client = CUMTDClient(api_key)
    coordinators = {}
    stops = entry.options.get(CONF_STOPS, [])

    for idx, stop in enumerate(stops):
        coordinator = CUMTDBusCoordinator(
            hass=hass,
            client=client,
            stop_id=stop[CONF_STOP_ID],
            stop_name=stop.get(CONF_STOP_NAME, stop[CONF_STOP_ID]),
            route_id=stop.get(CONF_ROUTE_ID),
            direction_filter=stop.get(CONF_DIRECTION_FILTER),
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[idx] = coordinator

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await _async_cleanup_orphaned_entities(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_orphaned_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove entities for stops that are no longer configured.

    HA doesn't automatically remove entities when config changes - we must
    explicitly check which stops still exist and clean up the rest.
    """
    entity_registry = er.async_get(hass)
    current_stops = entry.options.get(CONF_STOPS, [])

    valid_unique_ids = set()
    for stop in current_stops:
        stop_id = stop[CONF_STOP_ID]
        route_id = stop.get(CONF_ROUTE_ID) or "all"
        direction = stop.get(CONF_DIRECTION_FILTER) or "all"
        unique_id = f"{entry.entry_id}_{stop_id}_{route_id}_{direction}"
        valid_unique_ids.add(unique_id)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for entity_entry in entries:
        if entity_entry.unique_id not in valid_unique_ids:
            entity_registry.async_remove(entity_entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()

    return unload_ok
