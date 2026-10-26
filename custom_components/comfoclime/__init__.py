import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
import homeassistant.helpers.device_registry as dr

from .comfoclime_api import ComfoClimeAPI
from .coordinator import (
    ComfoClimeAlarmsCoordinator,
    ComfoClimeDashboardCoordinator,
    ComfoClimeThermalprofileCoordinator,
)
from .scenarios import (
    SCENARIO_DEFAULT_DURATIONS_MINUTES,
    SCENARIO_VALUES,
    async_activate_scenario,
)

DOMAIN = "comfoclime"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def _get_target_device_and_entry(
    hass: HomeAssistant, device_id: str
) -> tuple[dr.DeviceEntry, dict]:
    """Resolve a registered ComfoClime device to its loaded config entry."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError("The selected ComfoClime device was not found")

    device_uuid = next(
        (identifier for domain, identifier in device.identifiers if domain == DOMAIN),
        None,
    )
    if device_uuid is None:
        raise HomeAssistantError("The selected device is not a ComfoClime device")

    matches = []
    for entry_id in device.config_entries:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data is None:
            continue
        owned_uuids = {
            connected_device.get("uuid")
            for connected_device in entry_data.get("devices", [])
        }
        main_device = entry_data.get("main_device")
        if main_device:
            owned_uuids.add(main_device.get("uuid"))
        if device_uuid in owned_uuids:
            matches.append(entry_data)

    if len(matches) != 1:
        raise HomeAssistantError(
            "Could not uniquely identify the integration entry for this device"
        )
    return device, matches[0]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-wide services once for all config entries."""

    async def handle_set_property_service(call: ServiceCall) -> None:
        device, entry_data = _get_target_device_and_entry(hass, call.data["device_id"])
        device_uuid = next(
            identifier for domain, identifier in device.identifiers if domain == DOMAIN
        )
        api: ComfoClimeAPI = entry_data["api"]
        try:
            await api.async_set_property_for_device(
                hass,
                device_uuid=device_uuid,
                property_path=call.data["path"],
                value=call.data["value"],
                byte_count=call.data["byte_count"],
                signed=call.data.get("signed", True),
                faktor=call.data.get("faktor", 1.0),
            )
            _LOGGER.info(
                "Property %s set to %s for device %s",
                call.data["path"],
                call.data["value"],
                device_uuid,
            )
        except Exception as err:
            _LOGGER.exception("Failed to set property %s", call.data["path"])
            raise HomeAssistantError(
                f"Failed to set property {call.data['path']}: {err}"
            ) from err

    async def handle_reset_system_service(call: ServiceCall) -> None:
        device_id = call.data.get("device_id")
        if device_id:
            device, entry_data = _get_target_device_and_entry(hass, device_id)
            device_uuid = next(
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            )
            main_device = entry_data.get("main_device")
            if not main_device or main_device.get("uuid") != device_uuid:
                raise HomeAssistantError(
                    "Reset is only supported for the ComfoClime main device"
                )
        else:
            entries = [
                entry_data
                for entry_data in hass.data.get(DOMAIN, {}).values()
                if entry_data.get("main_device")
            ]
            if len(entries) != 1:
                raise HomeAssistantError(
                    "Select a ComfoClime device when more than one is configured"
                )
            entry_data = entries[0]
            device_uuid = entry_data["main_device"]["uuid"]
        api: ComfoClimeAPI = entry_data["api"]
        try:
            await api.async_reset_system(hass)
            _LOGGER.info("ComfoClime restart requested for %s", device_uuid)
        except Exception as err:
            _LOGGER.exception("Failed to restart ComfoClime device %s", device_uuid)
            raise HomeAssistantError(
                f"Failed to restart the ComfoClime device: {err}"
            ) from err

    async def handle_set_scenario_mode_service(call: ServiceCall) -> None:
        scenario = call.data["scenario"]
        if scenario not in SCENARIO_VALUES:
            raise HomeAssistantError(f"Unsupported ComfoClime scenario: {scenario}")

        device_id = call.data.get("device_id")
        if device_id:
            device, entry_data = _get_target_device_and_entry(hass, device_id)
            device_uuid = next(
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            )
            main_device = entry_data.get("main_device")
            if not main_device or main_device.get("uuid") != device_uuid:
                raise HomeAssistantError(
                    "Scenarios are supported only on the ComfoClime main device"
                )
        else:
            entries = [
                entry_data
                for entry_data in hass.data.get(DOMAIN, {}).values()
                if entry_data.get("main_device")
            ]
            if len(entries) != 1:
                raise HomeAssistantError(
                    "Select a ComfoClime device when more than one is configured"
                )
            entry_data = entries[0]
            device_uuid = entry_data["main_device"]["uuid"]

        duration_minutes = call.data.get("duration")
        if duration_minutes is None:
            duration_minutes = SCENARIO_DEFAULT_DURATIONS_MINUTES[scenario]
        if (
            isinstance(duration_minutes, bool)
            or not isinstance(duration_minutes, int)
            or not 1 <= duration_minutes <= 1440
        ):
            raise HomeAssistantError(
                "Scenario duration must be between 1 and 1440 minutes"
            )

        api: ComfoClimeAPI = entry_data["api"]
        try:
            activated = await async_activate_scenario(
                api,
                entry_data["coordinator"],
                hass,
                SCENARIO_VALUES[scenario],
                duration_minutes,
            )
        except Exception as err:
            _LOGGER.exception("Failed to set ComfoClime scenario %s", scenario)
            raise HomeAssistantError(
                f"Failed to set ComfoClime scenario {scenario}: {err}"
            ) from err

        if not activated:
            raise HomeAssistantError(
                f"ComfoClime did not activate scenario {scenario}. "
                "An active scenario may need to finish before another can start."
            )

        _LOGGER.info(
            "Scenario %s set for %s minutes on %s",
            scenario,
            duration_minutes,
            device_uuid,
        )

    async def handle_set_bypass_mode_service(call: ServiceCall) -> None:
        mode = call.data["mode"]
        device_id = call.data.get("device_id")

        if device_id:
            device, entry_data = _get_target_device_and_entry(hass, device_id)
            device_uuid = next(
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            )
            q_device = next(
                (
                    connected_device
                    for connected_device in entry_data.get("devices", [])
                    if connected_device.get("uuid") == device_uuid
                ),
                None,
            )
            if not q_device or q_device.get("modelTypeId") != 1:
                raise HomeAssistantError(
                    "Bypass control is only supported for a connected ComfoAir Q"
                )
        else:
            matches = [
                (entry_data, device)
                for entry_data in hass.data.get(DOMAIN, {}).values()
                for device in entry_data.get("devices", [])
                if device.get("modelTypeId") == 1
                and device.get("uuid") not in (None, "NULL")
            ]
            if len(matches) != 1:
                raise HomeAssistantError(
                    "Select a ComfoAir Q device when zero or multiple units are configured"
                )
            entry_data, q_device = matches[0]
            device_uuid = q_device["uuid"]

        duration_minutes = call.data.get("duration", 60)
        api: ComfoClimeAPI = entry_data["api"]
        try:
            await api.async_set_bypass_mode(
                hass,
                device_uuid=device_uuid,
                mode=mode,
                duration_minutes=duration_minutes,
            )
            if mode == "auto":
                _LOGGER.info("ComfoAir Q bypass returned to automatic mode")
            else:
                _LOGGER.info(
                    "ComfoAir Q bypass set to %s for %s minutes",
                    mode,
                    duration_minutes,
                )
        except Exception as err:
            _LOGGER.exception("Failed to set ComfoAir Q bypass mode to %s", mode)
            raise HomeAssistantError(
                f"Failed to set ComfoAir Q bypass mode to {mode}: {err}"
            ) from err

    async def handle_set_ventilation_mode_service(call: ServiceCall) -> None:
        mode = call.data["mode"]
        device_id = call.data.get("device_id")

        if device_id:
            device, entry_data = _get_target_device_and_entry(hass, device_id)
            device_uuid = next(
                identifier
                for domain, identifier in device.identifiers
                if domain == DOMAIN
            )
            q_device = next(
                (
                    connected_device
                    for connected_device in entry_data.get("devices", [])
                    if connected_device.get("uuid") == device_uuid
                ),
                None,
            )
            if not q_device or q_device.get("modelTypeId") != 1:
                raise HomeAssistantError(
                    "Ventilation mode control is only supported for a connected ComfoAir Q"
                )
        else:
            matches = [
                (entry_data, device)
                for entry_data in hass.data.get(DOMAIN, {}).values()
                for device in entry_data.get("devices", [])
                if device.get("modelTypeId") == 1
                and device.get("uuid") not in (None, "NULL")
            ]
            if len(matches) != 1:
                raise HomeAssistantError(
                    "Select a ComfoAir Q device when zero or multiple units are configured"
                )
            entry_data, q_device = matches[0]
            device_uuid = q_device["uuid"]

        duration_minutes = call.data.get("duration", 60)
        api: ComfoClimeAPI = entry_data["api"]
        try:
            await api.async_set_ventilation_mode(
                hass,
                device_uuid=device_uuid,
                mode=mode,
                duration_minutes=duration_minutes,
            )
            await entry_data["coordinator"].async_request_refresh()
            _LOGGER.info(
                "ComfoAir Q ventilation mode set to %s for %s minutes",
                mode,
                duration_minutes,
            )
        except Exception as err:
            _LOGGER.exception("Failed to set ComfoAir Q ventilation mode to %s", mode)
            raise HomeAssistantError(
                f"Failed to set ComfoAir Q ventilation mode to {mode}: {err}"
            ) from err

    hass.services.async_register(DOMAIN, "set_property", handle_set_property_service)
    hass.services.async_register(DOMAIN, "reset_system", handle_reset_system_service)
    hass.services.async_register(
        DOMAIN, "set_scenario_mode", handle_set_scenario_mode_service
    )
    hass.services.async_register(
        DOMAIN, "set_bypass_mode", handle_set_bypass_mode_service
    )
    hass.services.async_register(
        DOMAIN, "set_ventilation_mode", handle_set_ventilation_mode_service
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    host = entry.data["host"]
    api = ComfoClimeAPI(f"http://{host}", hass=hass, entry=entry)
    dashboard_coordinator = ComfoClimeDashboardCoordinator(hass, api)
    await dashboard_coordinator.async_config_entry_first_refresh()
    thermalprofile_coordinator = ComfoClimeThermalprofileCoordinator(hass, api)
    await thermalprofile_coordinator.async_config_entry_first_refresh()
    alarms_coordinator = ComfoClimeAlarmsCoordinator(hass, api)
    try:
        await alarms_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Reported alarm data unavailable during setup: %s", err)
    devices = await api.async_get_connected_devices(hass)
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": dashboard_coordinator,
        "tpcoordinator": thermalprofile_coordinator,
        "alarms_coordinator": alarms_coordinator,
        "devices": devices,
        "main_device": next(
            (device for device in devices if device.get("modelTypeId") == 20), None
        ),
    }

    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor", "binary_sensor", "switch", "number", "select", "fan", "climate"],
    )
    if (
        not hass.services.has_service(DOMAIN, "set_property")
        or not hass.services.has_service(DOMAIN, "set_scenario_mode")
        or not hass.services.has_service(DOMAIN, "set_bypass_mode")
        or not hass.services.has_service(DOMAIN, "set_ventilation_mode")
    ):
        await async_setup(hass, {})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["sensor", "binary_sensor", "switch", "number", "select", "fan", "climate"],
    )
    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "set_property")
        hass.services.async_remove(DOMAIN, "reset_system")
        hass.services.async_remove(DOMAIN, "set_scenario_mode")
        hass.services.async_remove(DOMAIN, "set_bypass_mode")
        hass.services.async_remove(DOMAIN, "set_ventilation_mode")
        hass.data.pop(DOMAIN)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
