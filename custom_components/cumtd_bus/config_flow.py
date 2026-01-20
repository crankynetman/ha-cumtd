"""Config flow for CUMTD Bus integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback

from .api import AuthenticationError, CUMTDAPIError, CUMTDClient
from .const import (
    CONF_API_KEY,
    CONF_CUSTOM_NAME,
    CONF_DIRECTION_FILTER,
    CONF_ROUTE_ID,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_STOPS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CUMTDBusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow: API key only, stops managed via options."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return CUMTDBusOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Initial setup: validate and store API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            client = CUMTDClient(api_key)
            try:
                await client.validate_api_key()
                return self.async_create_entry(
                    title="CUMTD Bus",
                    data={CONF_API_KEY: api_key},
                    options={CONF_STOPS: []},
                )

            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CUMTDAPIError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating API key")
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={
                "info": "Enter your CUMTD API key. You can add stops after setup."
            },
        )


class CUMTDBusOptionsFlow(config_entries.OptionsFlow):
    """Options flow: manage API key and stops."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._stop_data: dict[str, Any] = {}
        self._edit_index: int | None = None
        self._stop_search_results: dict[str, str] = {}

    def _get_stop_label(self, stop: dict[str, Any]) -> str:
        """Generate display label for a stop configuration."""
        if stop.get(CONF_CUSTOM_NAME):
            return stop[CONF_CUSTOM_NAME]
        stop_name = stop.get(CONF_STOP_NAME, "Unknown")
        route = stop.get(CONF_ROUTE_ID, "All Routes")
        return f"{stop_name} - {route}"

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Main menu: edit API key or manage stops."""
        stops = self._config_entry.options.get(CONF_STOPS, [])

        if user_input is not None:
            return await getattr(self, f"async_step_{user_input['next_step']}")()

        menu_options = ["edit_api_key", "add_stop"]
        if stops:
            menu_options.append("manage_stops")

        stop_list = []
        for idx, stop in enumerate(stops):
            stop_list.append(f"{idx + 1}. {self._get_stop_label(stop)}")

        description = f"API Key: {self._config_entry.data[CONF_API_KEY][:8]}..."
        if stop_list:
            description += f"\n\nConfigured Stops ({len(stops)}):\n" + "\n".join(stop_list)
        else:
            description += "\n\nNo stops configured yet. Click 'Add New Stop' to begin."

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
            description_placeholders={"description": description},
        )

    async def async_step_edit_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            new_key = user_input[CONF_API_KEY]
            client = CUMTDClient(new_key)
            try:
                await client.validate_api_key()
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={CONF_API_KEY: new_key},
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CUMTDAPIError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating new API key")
                errors["base"] = "unknown"
            finally:
                await client.close()

        current_key = self._config_entry.data[CONF_API_KEY]
        masked_key = f"{current_key[:8]}...{current_key[-4:]}"

        return self.async_show_form(
            step_id="edit_api_key",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"current_key": masked_key},
        )

    async def async_step_manage_stops(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a stop to manage."""
        stops = self._config_entry.options.get(CONF_STOPS, [])

        if not stops:
            return await self.async_step_init()

        if user_input is not None:
            self._edit_index = user_input["stop_index"]
            return await self.async_step_stop_action()

        # Build stop selection options
        stop_options = {idx: self._get_stop_label(stop) for idx, stop in enumerate(stops)}

        return self.async_show_form(
            step_id="manage_stops",
            data_schema=vol.Schema({vol.Required("stop_index"): vol.In(stop_options)}),
        )

    async def async_step_stop_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose to edit or remove the selected stop."""
        if user_input is not None:
            action = user_input["action"]
            if action == "edit":
                return await self.async_step_edit_stop()
            if action == "remove":
                if self._edit_index is None:
                    return await self.async_step_init()
                return await self.async_step_remove_stop(self._edit_index)

        stops = self._config_entry.options.get(CONF_STOPS, [])
        stop_label = self._get_stop_label(stops[self._edit_index])

        return self.async_show_form(
            step_id="stop_action",
            data_schema=vol.Schema(
                {vol.Required("action"): vol.In({"edit": "Edit", "remove": "Remove"})}
            ),
            description_placeholders={"stop_name": stop_label},
        )

    async def async_step_add_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new stop - search by name."""
        self._stop_data = {}
        return await self.async_step_stop_search(user_input)

    async def async_step_stop_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for a stop by name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if "stop_selection" in user_input:
                selected = user_input["stop_selection"]
                self._stop_data[CONF_STOP_ID] = selected
                if selected in self._stop_search_results:
                    self._stop_data[CONF_STOP_NAME] = self._stop_search_results[selected]
                return await self.async_step_stop_configure()

            if "search_query" in user_input:
                search_query = user_input["search_query"].strip()

                if not search_query:
                    errors["search_query"] = "empty_search"
                else:
                    client = CUMTDClient(self._config_entry.data[CONF_API_KEY])
                    try:
                        response = await client.get_stops_by_search(search_query)

                        if not response.stops:
                            errors["search_query"] = "no_stops_found"
                        else:
                            self._stop_search_results = {
                                stop.stop_id: stop.stop_name for stop in response.stops[:20]
                            }

                            stop_options = {
                                stop.stop_id: f"{stop.stop_name} ({stop.stop_id})"
                                for stop in response.stops[:20]
                            }

                            return self.async_show_form(
                                step_id="stop_search",
                                data_schema=vol.Schema(
                                    {vol.Required("stop_selection"): vol.In(stop_options)}
                                ),
                                description_placeholders={
                                    "search_results": f"Found {len(response.stops)} stops"
                                },
                            )
                    except CUMTDAPIError:
                        errors["base"] = "cannot_connect"
                    finally:
                        await client.close()

        return self.async_show_form(
            step_id="stop_search",
            data_schema=vol.Schema({vol.Required("search_query"): str}),
            errors=errors,
        )

    async def async_step_stop_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure route/direction filters and custom name."""
        errors: dict[str, str] = {}

        route_options = {"": "All routes"}
        direction_options = {"": " All directions"}

        client = CUMTDClient(self._config_entry.data[CONF_API_KEY])
        try:
            routes_response = await client.get_routes_by_stop(self._stop_data[CONF_STOP_ID])
            if routes_response.routes:
                unique_routes = {
                    route.route_short_name: route.route_short_name
                    for route in routes_response.routes
                    if route.route_short_name
                }
                route_options.update(sorted(unique_routes.items()))

            # Departures call is wrapped in try/except because CUMTD API sometimes
            # returns 500 errors for this endpoint (route list is more reliable)
            try:
                departures_response = await client.get_departures_by_stop(
                    self._stop_data[CONF_STOP_ID]
                )
                if departures_response.departures:
                    directions = sorted(
                        {dep.direction for dep in departures_response.departures if dep.direction}
                    )
                    direction_options.update({d: d for d in directions})
            except CUMTDAPIError:
                _LOGGER.debug(
                    "Could not fetch directions for stop %s", self._stop_data[CONF_STOP_ID]
                )

        except CUMTDAPIError:
            _LOGGER.exception("API error fetching routes for stop")
            errors["base"] = "cannot_connect"
        finally:
            await client.close()

        if user_input is None or errors:
            return self.async_show_form(
                step_id="stop_configure",
                data_schema=vol.Schema(
                    {
                        vol.Optional("route_id", default=""): vol.In(route_options),
                        vol.Optional("direction_filter", default=""): vol.In(direction_options),
                        vol.Optional("custom_name", default=""): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "stop_name": self._stop_data.get(CONF_STOP_NAME, "Unknown")
                },
            )

        self._stop_data[CONF_ROUTE_ID] = user_input.get("route_id") or None
        self._stop_data[CONF_DIRECTION_FILTER] = user_input.get("direction_filter") or None
        self._stop_data[CONF_CUSTOM_NAME] = user_input.get("custom_name") or None

        stops = list(self._config_entry.options.get(CONF_STOPS, []))
        if self._edit_index is not None:
            stops[self._edit_index] = self._stop_data
        else:
            stops.append(self._stop_data)

        return self.async_create_entry(title="", data={CONF_STOPS: stops})

    async def async_step_edit_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing stop."""
        stops = self._config_entry.options.get(CONF_STOPS, [])
        if self._edit_index is None or self._edit_index >= len(stops):
            return await self.async_step_init()

        self._stop_data = dict(stops[self._edit_index])
        return await self.async_step_stop_configure(None)

    async def async_step_remove_stop(self, idx: int) -> ConfigFlowResult:
        """Remove a stop from the list."""
        stops = list(self._config_entry.options.get(CONF_STOPS, []))
        if idx < len(stops):
            stops.pop(idx)
            return self.async_create_entry(title="", data={CONF_STOPS: stops})

        return await self.async_step_init()
