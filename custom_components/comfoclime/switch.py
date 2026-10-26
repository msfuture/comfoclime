import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .comfoclime_api import ComfoClimeAPI
from .coordinator import ComfoClimeThermalprofileCoordinator
from .coordinator import ComfoClimeDashboardCoordinator
from .entities.switch_definitions import SWITCHES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    host = entry.data["host"]
    api = ComfoClimeAPI(f"http://{host}")

    switches = []
    try:
        await api.async_get_uuid(hass)
    except Exception as e:
        _LOGGER.error(f"UUID konnte nicht geladen werden: {e}")
        return
    main_device = hass.data[DOMAIN][entry.entry_id]["main_device"]

    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    tpcoordinator = data["tpcoordinator"]
    dbcoordinator = data["coordinator"]
    try:
        await tpcoordinator.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.warning(f"Thermalprofile-Daten konnten nicht geladen werden: {e}")

    switches.extend(
        ComfoClimeModeSwitch(
            hass,
            tpcoordinator,
            api,
            s["key"],
            s["translation_key"],
            s["name"],
            device=main_device,
            entry=entry,
        )
        for s in SWITCHES
    )

    switches.append(
        ComfoClimeStandbySwitch(
            hass,
            dbcoordinator,
            api,
            device=main_device,
            entry=entry,
        )
    )

    async_add_entities(switches, True)


class ComfoClimeModeSwitch(
    CoordinatorEntity[ComfoClimeThermalprofileCoordinator], SwitchEntity
):
    def __init__(
        self,
        hass,
        coordinator,
        api,
        key,
        translation_key,
        name,
        device=None,
        entry=None,
    ):
        super().__init__(coordinator)
        self._hass = hass
        self._api = api
        self._key_path = key.split(".")
        self._name = name
        self._state = False
        self._device = device
        self._entry = entry
        self._attr_config_entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_switch_{key}"
        # self._attr_name = name
        self._attr_translation_key = translation_key
        self._attr_has_entity_name = True

    @property
    def is_on(self):
        return self._state

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
        data = self.coordinator.data
        try:
            # Zugriff auf verschachtelte Keys wie ["season"]["status"]
            val = data
            for key in self._key_path:
                val = val.get(key)
            self._state = val == 1
        except Exception as e:
            _LOGGER.error(f"Fehler beim Lesen des Switch-Zustands: {e}")
            self._state = None
        self.async_write_ha_state()

    def turn_on(self, **kwargs):
        self._set_status(1)

    def turn_off(self, **kwargs):
        self._set_status(0)

    def _set_status(self, value):
        # Leeres Grundobjekt mit null
        updates = {"season": {"status": None}, "temperature": {"status": None}}

        section = self._key_path[0]
        key = self._key_path[1]

        updates[section][key] = value

        try:
            self._api.update_thermal_profile(updates)
            self._state = value == 1
            self.hass.create_task(self.coordinator.async_request_refresh())

        except Exception as e:
            _LOGGER.error(f"Fehler beim Setzen von {self._name}: {e}")


class ComfoClimeStandbySwitch(
    CoordinatorEntity[ComfoClimeDashboardCoordinator], SwitchEntity
):
    def __init__(
        self,
        hass,
        coordinator,
        api,
        device=None,
        entry=None,
    ):
        super().__init__(coordinator)
        self._hass = hass
        self._api = api
        self._key_path = "hpstandby"
        self._name = "Heatpump on/off"
        self._state = False
        self._device = device
        self._entry = entry
        self._attr_config_entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_switch_hpstandby"
        # self._attr_name = name
        self._attr_translation_key = "heatpump_onoff"
        self._attr_has_entity_name = True

    @property
    def is_on(self):
        return self._state

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
        data = self.coordinator.data
        try:
            # Zugriff auf verschachtelte Keys wie ["season"]["status"]
            val = data.get("hpStandby")
            if val:
                val = False
            else:
                val = True
            self._state = val == 1
        except Exception as e:
            _LOGGER.error(f"Fehler beim Lesen des Switch-Zustands: {e}")
            self._state = None
        self.async_write_ha_state()

    def turn_on(self, **kwargs):
        self._set_status(1)

    def turn_off(self, **kwargs):
        self._set_status(0)

    def _set_status(self, value):
        try:
            if value == 0:
                self._api.update_dashboard(self.hass, hp_standby=True)
            if value == 1:
                self._api.update_dashboard(self.hass, hp_standby=False)
            self._state = value == 1
            self.hass.create_task(self.coordinator.async_request_refresh())

        except Exception as e:
            _LOGGER.error(f"Fehler beim Setzen von {self._name}: {e}")
