import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.device_registry as dr

from .comfoclime_api import ComfoClimeAPI
from .coordinator import (
    ComfoClimeDashboardCoordinator,
    ComfoClimeThermalprofileCoordinator,
)

DOMAIN = "comfoclime"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    return True  # wir nutzen keine YAML-Konfiguration mehr


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    host = entry.data["host"]
    api = ComfoClimeAPI(f"http://{host}", hass=hass, entry=entry)
    # Dashboard-Coordinator erstellen
    dashboard_coordinator = ComfoClimeDashboardCoordinator(hass, api)
    await dashboard_coordinator.async_config_entry_first_refresh()
    thermalprofile_coordinator = ComfoClimeThermalprofileCoordinator(hass, api)
    await thermalprofile_coordinator.async_config_entry_first_refresh()
    devices = await api.async_get_connected_devices(hass)
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": dashboard_coordinator,
        "tpcoordinator": thermalprofile_coordinator,
        "devices": devices,
        "main_device": next((d for d in devices if d.get("modelTypeId") == 20), None),
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "switch", "number", "select", "fan", "climate"]
    )

    async def handle_set_property_service(call: ServiceCall):
        device_id = call.data["device_id"]
        path = call.data["path"]
        value = call.data["value"]
        byte_count = call.data["byte_count"]
        signed = call.data.get("signed", True)
        faktor = call.data.get("faktor", 1.0)
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if not device or not device.identifiers:
            _LOGGER.error("Gerät nicht gefunden oder ungültig")
            return
        domain, device_uuid = list(device.identifiers)[0]
        if domain != DOMAIN:
            _LOGGER.error(f"Gerät gehört nicht zur Integration {DOMAIN}")
            return
        try:
            await api.async_set_property_for_device(
                hass,
                device_uuid=device_uuid,
                property_path=path,
                value=value,
                byte_count=byte_count,
                signed=signed,
                faktor=faktor,
            )
            _LOGGER.info(f"Property {path} auf {value} gesetzt für {device_uuid}")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Setzen von Property {path}: {e}")
            raise HomeAssistantError(f"Fehler beim Setzen von Property {path}: {e}")

    async def handle_reset_system_service(call: ServiceCall):
        try:
            await api.async_reset_system(hass)
            _LOGGER.info("ComfoClime Neustart ausgelöst")
        except Exception as e:
            _LOGGER.error(f"Fehler beim Neustart des Geräts: {e}")
            raise HomeAssistantError(f"Fehler beim Neustart des Geräts: {e}")

    async def handle_set_scenario_mode_service(call: ServiceCall):
        """Handle set_scenario_mode service call.

        This service activates special operating modes (scenarios) on the ComfoClime
        climate entity with optional custom duration.

        Supported scenarios:
        - cooking: High ventilation for cooking (default: 30 min)
        - party: High ventilation for parties (default: 30 min)
        - away: Reduced mode for vacation (default: 24 hours)
        - scenario_boost: Maximum power boost (default: 30 min)
        """
        entity_id = call.data["entity_id"]
        scenario = call.data["scenario"]
        duration = call.data.get("duration")
        start_delay = call.data.get("start_delay")

        # Validate scenario parameter
        from .climate import SCENARIO_REVERSE_MAPPING

        valid_scenarios = list(SCENARIO_REVERSE_MAPPING.keys())
        if scenario not in valid_scenarios:
            raise HomeAssistantError(
                f"Invalid scenario '{scenario}'. Must be one of: {', '.join(valid_scenarios)}"
            )

        # Validate duration if provided
        if duration is not None:
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise HomeAssistantError(
                    f"Duration must be a positive number, got: {duration}"
                )

        # Validate start_delay format if provided
        if start_delay is not None:
            if not isinstance(start_delay, str):
                raise HomeAssistantError(
                    f"start_delay must be a datetime string (e.g. 'YYYY-MM-DD HH:MM:SS'), got: {type(start_delay).__name__}"
                )

        _LOGGER.debug(
            f"Service call: set_scenario_mode for {entity_id}, "
            f"scenario={scenario}, duration={duration}, start_delay={start_delay}"
        )

        # Get climate entity from component
        # Access the entity via the state machine's entities
        component = hass.data.get("entity_components", {}).get("climate")
        if component:
            climate_entity = component.get_entity(entity_id)

            if climate_entity and hasattr(climate_entity, "async_set_scenario_mode"):
                try:
                    await climate_entity.async_set_scenario_mode(
                        scenario_mode=scenario,
                        duration=duration,
                        start_delay=start_delay,
                    )
                except Exception as e:
                    _LOGGER.exception(
                        f"Error setting scenario mode '{scenario}' on {entity_id}"
                    )
                    raise HomeAssistantError(
                        f"Failed to set scenario mode '{scenario}'"
                    ) from e
                else:
                    _LOGGER.info(
                        f"Scenario mode '{scenario}' activated for {entity_id} "
                        f"with duration {duration} and start_delay {start_delay}"
                    )
                    return

        # Entity not found or doesn't support scenarios
        raise HomeAssistantError(
            f"Climate entity '{entity_id}' not found or does not support scenario modes. "
            f"Make sure the entity exists and belongs to the ComfoClime integration."
        )

    hass.services.async_register(DOMAIN, "set_property", handle_set_property_service)
    hass.services.async_register(DOMAIN, "reset_system", handle_reset_system_service)
    hass.services.async_register(
        DOMAIN, "set_scenario_mode", handle_set_scenario_mode_service
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    await hass.config_entries.async_forward_entry_unload(entry, "number")
    await hass.config_entries.async_forward_entry_unload(entry, "select")
    await hass.config_entries.async_forward_entry_unload(entry, "fan")
    await hass.config_entries.async_forward_entry_unload(entry, "climate")
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_reload_entry(hass, entry):
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
