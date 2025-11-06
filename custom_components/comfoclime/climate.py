"""Climate platform for ComfoClime integration."""
import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .comfoclime_api import ComfoClimeAPI
from .coordinator import (
    ComfoClimeDashboardCoordinator,
    ComfoClimeThermalprofileCoordinator,
)


_LOGGER = logging.getLogger(__name__)

# Temperature Profile Presets
PRESET_MAPPING = {
    0: PRESET_COMFORT,
    1: PRESET_BOOST,
    2: PRESET_ECO,
}

PRESET_REVERSE_MAPPING = {v: k for k, v in PRESET_MAPPING.items()}

# Fan Mode Mapping (based on fan.py implementation)
# fanSpeed from dashboard: 0, 1, 2, 3
FAN_MODE_MAPPING = {
    0: FAN_OFF,     # Speed 0
    1: FAN_LOW,     # Speed 1
    2: FAN_MEDIUM,  # Speed 2
    3: FAN_HIGH,    # Speed 3
}

FAN_MODE_REVERSE_MAPPING = {v: k for k, v in FAN_MODE_MAPPING.items()}

# HVAC Mode Mapping (season values to HVAC modes)
# Season from dashboard: 0 (transitional), 1 (heating), 2 (cooling)
HVAC_MODE_MAPPING = {
    0: HVACMode.FAN_ONLY,  # transitional
    1: HVACMode.HEAT,      # heating
    2: HVACMode.COOL,      # cooling
}

# Reverse mapping for setting HVAC modes
# Maps HVAC mode to (season_value, hp_standby_value)
# Note: hpStandby=True means device is in standby (powered off), so OFF and FAN_ONLY use True
#       hpStandby=False means device is active (heating/cooling), so HEAT/COOL use False
HVAC_MODE_REVERSE_MAPPING = {
    HVACMode.OFF: (None, True),        # Turn off device via hpStandby (device in standby)
    HVACMode.FAN_ONLY: (0, True),      # Transitional season, device in standby (fan only)
    HVACMode.HEAT: (1, False),          # Heating season, device active
    HVACMode.COOL: (2, False),          # Cooling season, device active
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ComfoClime climate entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    api: ComfoClimeAPI = data["api"]
    dashboard_coordinator: ComfoClimeDashboardCoordinator = data["coordinator"]
    thermalprofile_coordinator: ComfoClimeThermalprofileCoordinator = data["tpcoordinator"]
    main_device: dict[str, Any] | None = data.get("main_device")

    if not main_device:
        _LOGGER.warning("No main device found - cannot create climate entity")
        return

    climate_entity = ComfoClimeClimate(
        dashboard_coordinator,
        thermalprofile_coordinator,
        api,
        main_device,
        config_entry
    )

    async_add_entities([climate_entity])


class ComfoClimeClimate(CoordinatorEntity[ComfoClimeDashboardCoordinator], ClimateEntity):
    """ComfoClime Climate entity."""

    def __init__(
        self,
        dashboard_coordinator: ComfoClimeDashboardCoordinator,
        thermalprofile_coordinator: ComfoClimeThermalprofileCoordinator,
        api: ComfoClimeAPI,
        device: dict[str, Any],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(dashboard_coordinator)
        self._api = api
        self._thermalprofile_coordinator = thermalprofile_coordinator
        self._device = device
        self._entry = entry

        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_name = None  # Use device name
        self._attr_has_entity_name = True
        self._attr_translation_key = "climate"

        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = 0.1
        self._attr_target_temperature_step = 0.5

        # Supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.FAN_MODE
        )

        # HVAC modes
        self._attr_hvac_modes = list(HVAC_MODE_REVERSE_MAPPING.keys())

        # Preset modes
        self._attr_preset_modes = list(PRESET_REVERSE_MAPPING.keys())

        # Fan modes
        self._attr_fan_modes = list(FAN_MODE_REVERSE_MAPPING.keys())

        # Add thermal profile coordinator listener
        self._thermalprofile_coordinator.async_add_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._thermalprofile_coordinator.last_update_success
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device["uuid"])},
            "name": self._device.get("displayName", "ComfoClime"),
            "manufacturer": "Zehnder",
            "model": self._device.get("@modelType", "ComfoClime"),
            "sw_version": self._device.get("version"),
        }

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from dashboard data."""
        if self.coordinator.data:
            return self.coordinator.data.get("indoorTemperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature from dashboard data.

        The dashboard provides setPointTemperature which reflects the current target.
        Falls back to thermal profile data if not available in dashboard.
        """
        # Primary source: dashboard setPointTemperature
        if self.coordinator.data:
            set_point = self.coordinator.data.get("setPointTemperature")
            if set_point is not None:
                return set_point

        # Fallback: thermal profile data for backward compatibility
        thermal_data = self._thermalprofile_coordinator.data
        if not thermal_data:
            return None

        temp_data = thermal_data.get("temperature", {})

        # Check temperature mode
        if self._get_temperature_status() == 0:
            # Manual mode: use manualTemperature from thermal profile
            return temp_data.get("manualTemperature")

        # Automatic mode: use comfort temperature based on season
        season = self._get_current_season()

        if season == 1:  # heating
            heating_data = thermal_data.get("heatingThermalProfileSeasonData", {})
            return heating_data.get("comfortTemperature")
        elif season == 2:  # cooling
            cooling_data = thermal_data.get("coolingThermalProfileSeasonData", {})
            return cooling_data.get("comfortTemperature")

        # Fallback: manual temperature (for transitional season)
        return temp_data.get("manualTemperature")

    @property
    def min_temp(self) -> float:
        """Return minimum temperature as per Copilot instructions."""
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return maximum temperature as per Copilot instructions."""
        return 30.0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode from dashboard data.

        Maps the season field from dashboard to HVAC mode:
        - season 0 (transitional) → FAN_ONLY
        - season 1 (heating) → HEAT
        - season 2 (cooling) → COOL
        - season None or unknown → OFF (default fallback)
        - hpStandby true + season None → OFF (device powered off)
        """
        if not self.coordinator.data:
            return HVACMode.OFF

        # Get season and hpStandby values
        hp_standby = self.coordinator.data.get("hpStandby")
        season = self.coordinator.data.get("season")

        # Check if device is in standby (powered off)
        # Only consider it OFF if hpStandby=True AND season is None
        # If season is set, respect the season even if hpStandby=True
        if hp_standby is True and season is None:
            return HVACMode.OFF

        # Map season from dashboard to HVAC mode using mapping
        # Falls back to OFF if season is None or unknown
        return HVAC_MODE_MAPPING.get(season, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action based on dashboard heatPumpStatus.

        Uses bitwise operations to determine the current action:
        - Bit 0 (0x01): Device is active/running
        - Bit 1 (0x02): Heating mode flag
        - Bit 2 (0x04): Cooling mode flag
        
        Heat pump status codes (from API documentation):
        Code | Binary      | Meaning
        -----|-------------|--------
        0    | 0000 0000  | Off
        1    | 0000 0001  | Starting up (active, no mode)
        3    | 0000 0011  | Heating (active + heating flag)
        5    | 0000 0101  | Cooling (active + cooling flag)
        17   | 0001 0001  | Transitional (active + other flags)
        19   | 0001 0011  | Heating + transitional state
        21   | 0001 0101  | Cooling + transitional state
        67   | 0100 0011  | Heating + other state
        75   | 0100 1011  | Heating + cooling + other
        83   | 0101 0011  | Heating + other state

        Reference: https://github.com/msfuture/comfoclime_api/blob/main/ComfoClimeAPI.md#heat-pump-status-codes
        """
        if not self.coordinator.data:
            return HVACAction.OFF

        heat_pump_status = self.coordinator.data.get("heatPumpStatus")

        if heat_pump_status is None or heat_pump_status == 0:
            return HVACAction.OFF

        # Bitwise operation to determine heating/cooling state
        # Bit 1 (0x02) indicates heating
        # Bit 2 (0x04) indicates cooling
        # If both bits are set (e.g., status 75), heating takes priority
        # This is intentional as heating typically has higher priority for safety
        is_heating = bool(heat_pump_status & 0x02)  # Check bit 1
        is_cooling = bool(heat_pump_status & 0x04)  # Check bit 2

        if is_heating:
            return HVACAction.HEATING
        elif is_cooling:
            return HVACAction.COOLING
        else:
            # Device is active but not heating or cooling (starting up or idle)
            return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode from dashboard data.

        Dashboard provides temperatureProfile directly, so we use that as primary source.
        Falls back to thermal profile coordinator for backward compatibility.
        """
        # Primary source: Dashboard data (most current)
        if self.coordinator.data:
            temp_profile = self.coordinator.data.get("temperatureProfile")
            if isinstance(temp_profile, int):
                return PRESET_MAPPING.get(temp_profile)
            if isinstance(temp_profile, str) and temp_profile.isdigit():
                return PRESET_MAPPING.get(int(temp_profile))

        # Fallback: Thermal Profile Coordinator (for backward compatibility)
        if self._thermalprofile_coordinator.data:
            temp_profile = self._thermalprofile_coordinator.data.get("temperatureProfile")
            if isinstance(temp_profile, int):
                return PRESET_MAPPING.get(temp_profile)
            if isinstance(temp_profile, str) and temp_profile.isdigit():
                return PRESET_MAPPING.get(int(temp_profile))

        return None

    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode from dashboard data.

        Maps fanSpeed from dashboard (0-3) to fan mode strings:
        - 0: off
        - 1: low
        - 2: medium
        - 3: high
        """
        if self.coordinator.data:
            fan_speed = self.coordinator.data.get("fanSpeed")
            if isinstance(fan_speed, int):
                return FAN_MODE_MAPPING.get(fan_speed)
            if isinstance(fan_speed, str) and fan_speed.isdigit():
                return FAN_MODE_MAPPING.get(int(fan_speed))
        return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self._attr_fan_modes

    def _get_temperature_status(self) -> int:
        """Get the temperature.status value from thermal profile.

        Returns:
            1 if automatic comfort temperature is enabled (default)
            0 if manual temperature mode is active
        """
        thermal_data = self._thermalprofile_coordinator.data
        if not thermal_data:
            return 1  # default to automatic

        temp_data = thermal_data.get("temperature", {})
        return temp_data.get("status", 1)

    def _get_current_season(self) -> int:
        """Get the current season value from dashboard or thermal profile.

        Returns:
            0 for transitional, 1 for heating, 2 for cooling
        """
        # Primary source: dashboard
        if self.coordinator.data:
            season = self.coordinator.data.get("season")
            if isinstance(season, int):
                return season

        # Fallback: thermal profile
        thermal_data = self._thermalprofile_coordinator.data
        if not thermal_data:
            return 0

        season_data = thermal_data.get("season", {})
        return season_data.get("season", 0)

    async def _async_refresh_coordinators(self) -> None:
        """Refresh both dashboard and thermal profile coordinators."""
        await self.coordinator.async_request_refresh()
        await self._thermalprofile_coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature via dashboard API.

        According to issue requirements, all temperature changes should be made via
        the dashboard API using setPointTemperature, not via thermalprofile.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("No temperature provided in kwargs")
            return

        try:
            _LOGGER.debug(f"Setting temperature to {temperature}°C via dashboard API")

            # Use consolidated dashboard update method
            await self.async_update_dashboard(set_point_temperature=temperature)

            # Request refresh of coordinators
            # Both coordinators are refreshed to ensure UI consistency
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set temperature to {temperature}")

    async def async_update_dashboard(
        self,
        set_point_temperature: float | None = None,
        fan_speed: int | None = None,
        season: int | None = None,
        hp_standby: bool | None = None,
        schedule: int | None = None,
    ) -> None:
        """Update dashboard settings via API.

        Consolidated method for all dashboard updates. Only fields that are provided
        (not None) will be included in the update payload.

        Args:
            set_point_temperature: Target temperature (°C)
            fan_speed: Fan speed (0-3)
            season: Season value (0=transitional, 1=heating, 2=cooling)
            hp_standby: Heat pump standby state (True=standby/off, False=active)
            schedule: Schedule mode
        """
        import requests

        if not self._api.uuid:
            await self.hass.async_add_executor_job(self._api.get_uuid)

        def _update():
            # Build payload with only fields documented in the ComfoClime API spec
            # Fields like scenario, scenarioTimeLeft, @type, name, displayName, description
            # are NOT part of the official API and should not be included
            payload = {
                "setPointTemperature": set_point_temperature,
                "fanSpeed": fan_speed,
                "season": season,
                "schedule": schedule,
            }

            # Add hpStandby only if provided (to maintain backward compatibility)
            if hp_standby is not None:
                payload["hpStandby"] = hp_standby

            headers = {"content-type": "application/json; charset=utf-8"}
            url = f"{self._api.base_url}/system/{self._api.uuid}/dashboard"
            try:
                response = requests.put(url, json=payload, timeout=5, headers=headers)
                response.raise_for_status()
                _LOGGER.debug(f"Dashboard updated: {payload}")
            except Exception as e:
                _LOGGER.error(f"Error updating dashboard: {e}")
                raise

        await self.hass.async_add_executor_job(_update)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode by updating season and hpStandby via dashboard API."""
        try:
            # Use HVAC_MODE_REVERSE_MAPPING to get season and hpStandby values
            if hvac_mode not in HVAC_MODE_REVERSE_MAPPING:
                _LOGGER.error(f"Unsupported HVAC mode: {hvac_mode}")
                return

            season_value, hp_standby_value = HVAC_MODE_REVERSE_MAPPING[hvac_mode]

            # Update season and hpStandby via consolidated dashboard method
            await self.async_update_dashboard(season=season_value, hp_standby=hp_standby_value)

            # Request refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set HVAC mode {hvac_mode}")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode by updating temperature profile."""
        if preset_mode not in PRESET_REVERSE_MAPPING:
            _LOGGER.error(f"Unknown preset mode: {preset_mode}")
            return

        try:
            # Map preset mode to temperature profile value
            temperature_profile = PRESET_REVERSE_MAPPING[preset_mode]

            # Use working API method to set device setting
            await self.hass.async_add_executor_job(
                self._api.set_device_setting, temperature_profile
            )

            # Request refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set preset mode {preset_mode}")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode by updating fan speed in dashboard.

        Maps fan mode strings to fanSpeed values:
        - auto: 0
        - low: 1
        - medium: 2
        - high: 3
        """
        if fan_mode not in FAN_MODE_REVERSE_MAPPING:
            _LOGGER.error(f"Unknown fan mode: {fan_mode}")
            return

        try:
            # Map fan mode to fan speed value
            fan_speed = FAN_MODE_REVERSE_MAPPING[fan_mode]

            # Use API method to set fan speed via dashboard
            # set_device_setting(temperature_profile, fan_speed)
            # First parameter (temperature_profile) is None to only update fan speed
            await self.hass.async_add_executor_job(
                self._api.set_device_setting, None, fan_speed
            )

            # Request refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set fan mode {fan_mode}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all interface data as extra state attributes.

        Exposes all available data from the ComfoClime API interfaces:
        - Dashboard data from /system/{UUID}/dashboard
        - Thermal profile data from /system/{UUID}/thermalprofile
        """
        attrs = {}

        # Add complete dashboard data from Dashboard API interface
        if self.coordinator.data:
            attrs["dashboard"] = self.coordinator.data

        # Add complete thermal profile data from Thermal Profile API interface
        if self._thermalprofile_coordinator.data:
            attrs["thermal_profile"] = self._thermalprofile_coordinator.data

        return attrs
