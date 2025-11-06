import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .comfoclime_api import ComfoClimeAPI
from .coordinator import ComfoClimeThermalprofileCoordinator
from .entities.select_definitions import PROPERTY_SELECT_ENTITIES, SELECT_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    host = entry.data["host"]
    api = ComfoClimeAPI(f"http://{host}")
    await api.async_get_uuid(hass)

    devices = hass.data[DOMAIN][entry.entry_id]["devices"]
    main_device = hass.data[DOMAIN][entry.entry_id]["main_device"]

    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    tpcoordinator = data["tpcoordinator"]
    try:
        await tpcoordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.warning(f"Thermalprofile-Daten konnten nicht geladen werden: {e}")

    entities = [
        ComfoClimeSelect(
            hass, tpcoordinator, api, conf, device=main_device, entry=entry
        )
        for conf in SELECT_ENTITIES
    ]

    # Verbundene Geräte abrufen
    try:
        devices = hass.data[DOMAIN][entry.entry_id]["devices"]
    except Exception as e:
        _LOGGER.warning(f"Verbundene Geräte konnten nicht geladen werden: {e}")
        devices = []

    for device in devices:
        model_id = device.get("modelTypeId")
        dev_uuid = device.get("uuid")
        if dev_uuid == "NULL":
            continue

        select_defs = PROPERTY_SELECT_ENTITIES.get(model_id)
        if not select_defs:
            continue

        entities.extend(
            ComfoClimePropertySelect(
                hass=hass, api=api, conf=select_def, device=device, entry=entry
            )
            for select_def in select_defs
        )
    async_add_entities(entities, True)


class ComfoClimeSelect(
    CoordinatorEntity[ComfoClimeThermalprofileCoordinator], SelectEntity
):
    def __init__(self, hass, coordinator, api, conf, device=None, entry=None):
        super().__init__(coordinator)
        self._hass = hass
        self._api = api
        self._key = conf["key"]
        self._name = conf["name"]
        self._key_path = self._key.split(".")
        self._options_map = conf["options"]
        self._options_reverse = {v: k for k, v in self._options_map.items()}
        self._current = None
        self._device = device
        self._entry = entry
        self._attr_config_entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_select_{conf['key']}"
        # self._attr_name = conf["name"]
        self._attr_translation_key = conf["translation_key"]
        self._attr_has_entity_name = True

    @property
    def options(self):
        return list(self._options_map.values())

    @property
    def current_option(self):
        return self._current

    @property
    def device_info(self) -> DeviceInfo:
        if not self._device:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device["uuid"])},
            name=self._device.get("displayName", "ComfoClime"),
            manufacturer="Zehnder",
            model=self._device.get("@modelType"),
            sw_version=self._device.get("version", None),
        )

    def _handle_coordinator_update(self):
        try:
            data = self.coordinator.data
            val = data
            for k in self._key_path:
                val = val.get(k)
            self._current = self._options_map.get(val)
        except Exception as e:
            _LOGGER.error(f"Fehler beim Laden von {self._name}: {e}")
        self.async_write_ha_state()

    def select_option(self, option: str):
        value = self._options_reverse.get(option)
        if value is None:
            return

        try:
            if self._key == "temperatureProfile":
                # Use working API method for temperature profile (preset mode)
                self._api.set_device_setting(temperature_profile=value)
            else:
                section = self._key_path[0]
                key = self._key_path[1]
                updates = {section: {key: value}}
                self._api.update_thermal_profile(updates)

            self._current = option
            self._hass.add_job(self.coordinator.async_request_refresh)
        except Exception as e:
            _LOGGER.error(f"Fehler beim Setzen von {self._name}: {e}")


class ComfoClimePropertySelect(SelectEntity):
    def __init__(self, hass, api, conf, device=None, entry=None):
        self._hass = hass
        self._api = api
        self._name = conf["name"]
        self._options_map = conf["options"]
        self._options_reverse = {v: k for k, v in self._options_map.items()}
        self._current = None
        self._device = device
        self._entry = entry
        self._path = conf["path"]
        self._attr_config_entry_id = entry.entry_id
        self._attr_unique_id = (
            f"{entry.entry_id}_select_{conf['path'].replace('/', '_')}"
        )
        self._attr_translation_key = conf["translation_key"]
        self._attr_has_entity_name = True

    @property
    def options(self):
        return list(self._options_map.values())

    @property
    def current_option(self):
        return self._current

    @property
    def device_info(self) -> DeviceInfo:
        if not self._device:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device["uuid"])},
            name=self._device.get("displayName", "ComfoClime"),
            manufacturer="Zehnder",
            model=self._device.get("@modelType"),
            sw_version=self._device.get("version", None),
        )

    async def async_update(self):
        try:
            val = await self._api.async_read_property_for_device(
                self._hass, self._device["uuid"], self._path, byte_count=1
            )
            self._current = self._options_map.get(val)
        except Exception as e:
            _LOGGER.error(f"Fehler beim Laden von {self._name}: {e}")

    def select_option(self, option: str):
        value = self._options_reverse.get(option)
        if value is None:
            return

        try:
            self._api.set_property_for_device(
                self._device["uuid"], self._path, value, byte_count=1
            )
            self._current = option

        except Exception as e:
            _LOGGER.error(f"Fehler beim Setzen von {self._name}: {e}")
