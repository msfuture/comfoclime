import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow

DOMAIN = "comfoclime"


class ComfoClimeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            url = f"http://{host}/monitoring/ping"

            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(url, timeout=5) as resp,
                ):
                    if resp.status == 200:
                        data = await resp.json()
                        if "uuid" in data:
                            return self.async_create_entry(
                                title=f"ComfoClime @ {host}",
                                data={"host": host},
                            )
                        else:
                            errors["host"] = "no_uuid"
                    else:
                        errors["host"] = "no_response"
            except (TimeoutError, aiohttp.ClientError):
                errors["host"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("host", default="comfoclime.local"): str}
            ),
            errors=errors,
        )

    @classmethod
    def async_get_options_flow(cls, entry: ConfigEntry):
        return ComfoClimeOptionsFlow(entry)


class ComfoClimeOptionsFlow(OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "enable_diagnostics",
                        default=self.entry.options.get("enable_diagnostics", False),
                    ): bool,
                    vol.Optional(
                        "minimal_mode",
                        default=self.entry.options.get("minimal_mode", False),
                    ): bool,
                    vol.Optional(
                        "throttle_comfonet",
                        default=self.entry.options.get("throttle_comfonet", False),
                    ): bool,
                }
            ),
        )
