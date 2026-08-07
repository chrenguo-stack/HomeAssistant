from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, validate_system_id


class GreenhouseHistoryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            try:
                system_id = validate_system_id(str(user_input["system_id"]))
            except (KeyError, ValueError):
                errors["base"] = "invalid_system_id"
            else:
                await self.async_set_unique_id(system_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Greenhouse history ({system_id})",
                    data={"system_id": system_id},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("system_id"): str}),
            errors=errors,
        )
