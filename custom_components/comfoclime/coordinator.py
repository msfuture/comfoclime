from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)


class ComfoClimeDashboardCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="ComfoClime Dashboard",
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.async_get_dashboard_data(self.hass)
        except Exception as e:
            _LOGGER.warning(f"Fehler beim Abrufen der Dashboard-Daten: {e}")
            raise UpdateFailed(f"Fehler beim Abrufen der Dashboard-Daten: {e}")


class ComfoClimeThermalprofileCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="ComfoClime Thermalprofile",
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.async_get_thermal_profile(self.hass)
        except Exception as e:
            raise UpdateFailed(f"Fehler beim Abrufen der Thermalprofile-Daten: {e}")


class ComfoClimeAlarmsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="ComfoClime Reported Alarms",
            update_interval=timedelta(seconds=60),
        )
        self.api = api

    async def _async_update_data(self):
        try:
            return await self.api.async_get_alarms(self.hass)
        except Exception as e:
            _LOGGER.warning("Fehler beim Abrufen der Alarmcodes: %s", e)
            raise UpdateFailed(f"Fehler beim Abrufen der Alarmcodes: {e}") from e
