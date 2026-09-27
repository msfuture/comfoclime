import logging
from functools import partial

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


def _resolve_device_entry(hass: HomeAssistant, device_id: str) -> tuple[str, dict]:
    device = dr.async_get(hass).async_get(device_id)
    if not device:
        raise HomeAssistantError("Gerät nicht gefunden")

    device_identifier = next(
        (identifier for identifier in device.identifiers if identifier[0] == DOMAIN),
        None,
    )
    if not device_identifier:
        raise HomeAssistantError(f"Gerät gehört nicht zur Integration {DOMAIN}")

    _, device_uuid = device_identifier
    entries = hass.data.get(DOMAIN, {})
    for entry_id in device.config_entries:
        entry_data = entries.get(entry_id)
        if not isinstance(entry_data, dict) or "api" not in entry_data:
            continue

        return device_uuid, entry_data

    raise HomeAssistantError(
        "Das ausgewählte Gerät gehört zu keiner geladenen ComfoClime-Instanz"
    )


async def _async_handle_reset_system_service(hass: HomeAssistant, call: ServiceCall):
    device_uuid, entry_data = _resolve_device_entry(hass, call.data["device_id"])

    main_device = entry_data.get("main_device")
    if not main_device or main_device.get("uuid") != device_uuid:
        raise HomeAssistantError(
            "Das ausgewählte Gerät ist kein ComfoClime-Hauptgerät einer geladenen Instanz"
        )

    try:
        await entry_data["api"].async_reset_system(hass)
        _LOGGER.info("ComfoClime Neustart ausgelöst für %s", device_uuid)
    except Exception as err:
        _LOGGER.error("Fehler beim Neustart des Geräts: %s", err)
        raise HomeAssistantError(f"Fehler beim Neustart des Geräts: {err}") from err


async def _async_handle_set_property_service(hass: HomeAssistant, call: ServiceCall):
    device_uuid, entry_data = _resolve_device_entry(hass, call.data["device_id"])
    path = call.data["path"]
    value = call.data["value"]
    byte_count = call.data["byte_count"]
    signed = call.data.get("signed", True)
    faktor = call.data.get("faktor", 1.0)

    try:
        await entry_data["api"].async_set_property_for_device(
            hass,
            device_uuid=device_uuid,
            property_path=path,
            value=value,
            byte_count=byte_count,
            signed=signed,
            faktor=faktor,
        )
        _LOGGER.info("Property %s auf %s gesetzt für %s", path, value, device_uuid)
    except Exception as err:
        _LOGGER.error("Fehler beim Setzen von Property %s: %s", path, err)
        raise HomeAssistantError(
            f"Fehler beim Setzen von Property {path}: {err}"
        ) from err


async def async_setup(hass: HomeAssistant, config: dict):
    hass.services.async_register(
        DOMAIN,
        "reset_system",
        partial(_async_handle_reset_system_service, hass),
    )
    hass.services.async_register(
        DOMAIN,
        "set_property",
        partial(_async_handle_set_property_service, hass),
    )
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
