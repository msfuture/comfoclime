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
    PRESET_NONE,
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
# status=0 (manual mode) maps to PRESET_NONE (Manual)
# status=1 (automatic mode) uses temperatureProfile values:
PRESET_MAPPING = {
    0: PRESET_COMFORT,
    1: PRESET_BOOST,
    2: PRESET_ECO,
}

PRESET_REVERSE_MAPPING = {v: k for k, v in PRESET_MAPPING.items()}

# Add manual preset mode (status=0)
PRESET_MANUAL = PRESET_NONE  # "none" preset means manual temperature control

# Fan Mode Mapping (based on fan.py implementation)
# fanSpeed from dashboard: 0, 1, 2, 3
FAN_MODE_MAPPING = {
    0: FAN_OFF,  # Speed 0
    1: FAN_LOW,  # Speed 1
    2: FAN_MEDIUM,  # Speed 2
    3: FAN_HIGH,  # Speed 3
}

FAN_MODE_REVERSE_MAPPING = {v: k for k, v in FAN_MODE_MAPPING.items()}

# HVAC Mode Mapping (season values to HVAC modes)
# Season from dashboard: 0 (transition), 1 (heating), 2 (cooling)
HVAC_MODE_MAPPING = {
    0: HVACMode.FAN_ONLY,  # transition
    1: HVACMode.HEAT,  # heating
    2: HVACMode.COOL,  # cooling
}

# Reverse mapping for setting HVAC modes
# Maps HVAC mode to season value (0=transition, 1=heating, 2=cooling)
# OFF mode is handled separately via hpStandby field
HVAC_MODE_REVERSE_MAPPING = {
    HVACMode.OFF: None,  # Turn off device via hpStandby=True
    HVACMode.FAN_ONLY: 0,  # Transitional season (fan only)
    HVACMode.HEAT: 1,  # Heating season
    HVACMode.COOL: 2,  # Cooling season
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
    thermalprofile_coordinator: ComfoClimeThermalprofileCoordinator = data[
        "tpcoordinator"
    ]
    main_device: dict[str, Any] | None = data.get("main_device")

    if not main_device:
        _LOGGER.warning("No main device found - cannot create climate entity")
        return

    climate_entity = ComfoClimeClimate(
        dashboard_coordinator,
        thermalprofile_coordinator,
        api,
        main_device,
        config_entry,
    )

    async_add_entities([climate_entity])


class ComfoClimeClimate(
    CoordinatorEntity[ComfoClimeDashboardCoordinator], ClimateEntity
):
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

        # Preset modes (automatic profiles + manual mode)
        self._attr_preset_modes = [PRESET_MANUAL] + list(PRESET_REVERSE_MAPPING.keys())

        # Fan modes
        self._attr_fan_modes = list(FAN_MODE_REVERSE_MAPPING.keys())

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass, register listeners for both coordinators."""
        await super().async_added_to_hass()

        # Also listen to thermal profile coordinator updates
        # This ensures target_temperature updates are reflected immediately
        self.async_on_remove(
            self._thermalprofile_coordinator.async_add_listener(
                self._handle_coordinator_update
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update internal state from coordinator data
        # This ensures the entity reflects the latest data from ComfoClime
        try:
            if self.coordinator.data:
                _LOGGER.debug(f"Coordinator update received: {self.coordinator.data}")
        except Exception:
            _LOGGER.exception("Fehler beim Verarbeiten der Coordinator-Daten")

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Climate entity depends on both dashboard and thermal profile coordinators,
        so we check both for successful updates.
        """
        return (
            self.coordinator.last_update_success
            or self._thermalprofile_coordinator.last_update_success
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
        """Return target temperature for display.

        Uses manualTemperature from thermal profile as the display value.
        This represents the last set temperature.
        """
        tp = self._thermalprofile_coordinator.data or {}
        temp = (tp.get("temperature") or {}).get("manualTemperature")
        if isinstance(temp, (int, float)):
            return temp
        return None

    @property
    def min_temp(self) -> float:
        """Return minimum temperature as per system requirements."""
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return maximum temperature as per system requirements."""
        return 30.0

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode from dashboard data.

        Maps the season field from dashboard to HVAC mode:
        - season 0 (transition) → FAN_ONLY
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

        # If device is in standby (powered off), always report OFF regardless of season
        if hp_standby is True:
            return HVACMode.OFF

        # Map season from dashboard to HVAC mode using mapping
        # Falls back to OFF if season is None or unknown
        return HVAC_MODE_MAPPING.get(season, HVACMode.OFF)

    @property
    def hvac_action(self) -> list[HVACAction]:
        """Return current HVAC action based on dashboard heatPumpStatus.

        Heat pump status codes (from API documentation):

        Bit-Mapping:
        Bit         | 7    | 6          | 5    | 4          | 3              | 2       | 1       | 0
        ------------|------|------------|------|------------|----------------|---------|---------|-----
        Value (dec) | 128  | 64         | 32   | 16         | 8              | 4       | 2       | 1
        Value (hex) | 0x80 | 0x40       | 0x20 | 0x10       | 0x08           | 0x04    | 0x02    | 0x01
        Meaning     | IDLE | DEFROSTING | IDLE | DRYING (?) | PREHEATING (?) | COOLING | HEATING | IDLE

        Reference: https://github.com/msfuture/comfoclime_api/blob/main/ComfoClimeAPI.md#heat-pump-status-codes
        """
        if not self.coordinator.data:
            return [HVACAction.OFF]

        heat_pump_status = self.coordinator.data.get("heatPumpStatus")

        if heat_pump_status in [None, 0]:
            return [HVACAction.OFF]

        status_mapping = {
            0x02: HVACAction.HEATING,
            0x04: HVACAction.COOLING,
            0x08: HVACAction.PREHEATING,  # Not sure
            0x10: HVACAction.DRYING,  # Not sure
            0x20: HVACAction.IDLE,  # Unused
            0x40: HVACAction.DEFROSTING,  # Not sure
            0x80: HVACAction.IDLE,  # Unused
        }

        active_flags = [
            status for mask, status in status_mapping.items() if heat_pump_status & mask
        ]

        if not active_flags:
            return [HVACAction.IDLE]

        return active_flags

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode from dashboard data.

        Returns PRESET_MANUAL (none) if in manual mode (status=0 or setPointTemperature is set).
        Returns preset name (comfort/boost/eco) if in automatic mode (status=1).
        """
        if not self.coordinator.data:
            return None

        # Check if in manual mode by presence of setPointTemperature
        # or explicit status field (status=0 means manual mode)
        set_point = self.coordinator.data.get("setPointTemperature")
        status = self.coordinator.data.get("status")

        # Manual mode: setPointTemperature is set or status=0
        if set_point is not None or status == 0:
            return PRESET_MANUAL

        # Automatic mode: return the temperatureProfile preset
        temp_profile = self.coordinator.data.get("temperatureProfile")
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

    def _get_current_season(self) -> int:
        """Get the current season value from dashboard.

        Returns:
            0 for transition, 1 for heating, 2 for cooling
        """
        if self.coordinator.data:
            season = self.coordinator.data.get("season")
            if isinstance(season, int):
                return season
        return 0

    async def _async_refresh_coordinators(self) -> None:
        """Refresh both dashboard and thermal profile coordinators.

        Schedules non-blocking refresh of both coordinators to prevent blocking
        user interactions. The coordinators will update in the background and
        trigger entity updates via their listeners when ready.
        """
        # Schedule non-blocking refresh for both coordinators
        # This prevents the UI from becoming unresponsive while waiting for updates
        self.hass.async_create_task(self.coordinator.async_request_refresh())
        self.hass.async_create_task(
            self._thermalprofile_coordinator.async_request_refresh()
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature via dashboard API in manual mode.

        Setting a manual temperature activates manual mode (status=0) and replaces
        the preset profiles (seasonProfile, temperatureProfile) with setPointTemperature.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning("No temperature provided in kwargs")
            return

        try:
            _LOGGER.debug(
                f"Setting manual temperature to {temperature}°C via dashboard API"
            )

            # Setting setPointTemperature should explicitly switch to manual mode (status=0)
            # and replaces seasonProfile/temperatureProfile. We send status=0 to ensure
            # the device leaves automatic preset control when user changes temperature.
            await self.async_update_dashboard(
                set_point_temperature=temperature,
                status=0,
            )

            # Schedule non-blocking refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set temperature to {temperature}")

    async def async_update_dashboard(self, **kwargs) -> None:
        """Update dashboard settings via API.

        Wrapper method that delegates to the API's update_dashboard method.
        This ensures all dashboard updates go through the centralized API method.

        Args:
            **kwargs: Dashboard fields to update (set_point_temperature, fan_speed,
                     season, hp_standby, schedule, temperature_profile,
                     season_profile, status)
        """
        await self._api.async_update_dashboard(self.hass, **kwargs)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode by updating season via thermal profile API.

        The HVAC mode is determined by the season field in the thermal profile:
        - OFF: Sets hpStandby=True via dashboard (device off)
        - FAN_ONLY: Sets season=0 (transition) via thermal profile, hpStandby=False
        - HEAT: Sets season=1 (heating) via thermal profile, hpStandby=False
        - COOL: Sets season=2 (cooling) via thermal profile, hpStandby=False
        """
        try:
            # Use HVAC_MODE_REVERSE_MAPPING to get season value
            if hvac_mode not in HVAC_MODE_REVERSE_MAPPING:
                _LOGGER.error(f"Unsupported HVAC mode: {hvac_mode}")
                return

            season_value = HVAC_MODE_REVERSE_MAPPING[hvac_mode]

            # OFF mode: Set hpStandby=True via dashboard to turn off the device
            if hvac_mode == HVACMode.OFF:
                _LOGGER.debug("Setting HVAC mode to OFF - setting hpStandby=True")
                await self.async_update_dashboard(hp_standby=True)
            else:
                # Active modes: Use atomic operation to set both season and hpStandby
                # This prevents race conditions between thermal profile and dashboard updates
                _LOGGER.debug(
                    f"Setting HVAC mode to {hvac_mode} - "
                    f"atomically setting season={season_value} and hpStandby=False"
                )
                await self._api.async_set_hvac_season(
                    self.hass, season=season_value, hp_standby=False
                )

            # Schedule non-blocking refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set HVAC mode {hvac_mode}")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode via dashboard API.

        Setting PRESET_MANUAL (none) switches to manual temperature control mode.
        Setting other presets (comfort/boost/eco) activates automatic mode with
        both seasonProfile and temperatureProfile set to the selected preset value.
        """
        try:
            # Manual mode: User wants to use manual temperature control
            if preset_mode == PRESET_MANUAL:
                _LOGGER.debug(
                    "Switching to manual temperature control mode - "
                    "user needs to set temperature manually"
                )
                # Set status=0 to activate manual mode
                # setPointTemperature should be set separately via async_set_temperature
                await self.async_update_dashboard(status=0)

                # Schedule non-blocking refresh of coordinators
                await self._async_refresh_coordinators()
                return

            # Automatic mode with preset profile
            if preset_mode not in PRESET_REVERSE_MAPPING:
                _LOGGER.error(f"Unknown preset mode: {preset_mode}")
                return

            # Map preset mode to profile value (0=comfort, 1=boost, 2=eco)
            profile_value = PRESET_REVERSE_MAPPING[preset_mode]

            _LOGGER.debug(
                f"Setting preset mode to {preset_mode} (profile={profile_value}) "
                f"via dashboard API - activates automatic mode"
            )

            # Set both temperatureProfile and seasonProfile to the preset value
            # and activate automatic mode (status=1)
            # This replaces setPointTemperature with preset-based control
            await self.async_update_dashboard(
                temperature_profile=profile_value,
                season_profile=profile_value,
                status=1,
            )

            # Schedule non-blocking refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set preset mode {preset_mode}")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode by updating fan speed via dashboard API.

        Maps fan mode strings to fanSpeed values:
        - off: 0
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

            # Update fan speed via dashboard API
            await self.async_update_dashboard(fan_speed=fan_speed)

            # Schedule non-blocking refresh of coordinators
            await self._async_refresh_coordinators()

        except Exception:
            _LOGGER.exception(f"Failed to set fan mode {fan_mode}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return dashboard data as extra state attributes.

        Exposes all available data from the ComfoClime Dashboard API interface:
        - Dashboard data from /system/{UUID}/dashboard
        """
        attrs = {}

        # Add complete dashboard data from Dashboard API interface
        if self.coordinator.data:
            attrs["dashboard"] = self.coordinator.data

        # For transparency: expose last_manual_temperature from thermal profile if available
        tp = getattr(self._thermalprofile_coordinator, "data", None) or {}
        manual_temp = (tp.get("temperature") or {}).get("manualTemperature")
        if isinstance(manual_temp, (int, float)):
            attrs["last_manual_temperature"] = manual_temp

        return attrs
