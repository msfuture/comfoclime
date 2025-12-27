# comfoclime_api.py
import asyncio
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

_LOGGER = logging.getLogger(__name__)


class ComfoClimeAPI:
    def __init__(self, base_url, hass=None, entry=None):
        self.hass = hass
        self.base_url = base_url.rstrip("/")
        self.uuid = None
        self._request_lock = asyncio.Lock()
        self.entry = entry

    @staticmethod
    def bytes_to_signed_int(
        data: list, byte_count: int = None, signed: bool = True
    ) -> int:
        """Convert raw bytes to a signed integer value.

        Args:
            data: List of bytes (integers 0-255)
            byte_count: Number of bytes to read. If None calculate from data

        Returns:
            Signed integer value

        Raises:
            ValueError: If byte_count is not 1 or 2
        """
        if not isinstance(data, list):
            raise ValueError("'data' is not a list")

        if byte_count is None:
            byte_count = len(data)

        if byte_count not in (1, 2):
            raise ValueError(f"Unsupported byte count: {byte_count}")

        return int.from_bytes(data[:byte_count], byteorder="little", signed=signed)

    @staticmethod
    def signed_int_to_bytes(
        data: int, byte_count: int = 2, signed: bool = False
    ) -> list:
        """Convert a signed integer to a list of bytes.

        Args:
            data: Signed integer value
            byte_count: Number of bytes to convert to (1 or 2)

        Returns:
            List of bytes (integers 0-255)

        Raises:
            ValueError: If byte_count is not 1 or 2
        """
        if byte_count not in (1, 2):
            raise ValueError(f"Unsupported byte count: {byte_count}")

        return list(data.to_bytes(byte_count, byteorder="little", signed=signed))

    @staticmethod
    def fix_signed_temperature(api_value: float) -> float:
        """Fix temperature value by converting through signed 16-bit integer.

        This handles the case where temperature values need to be interpreted
        as signed 16-bit integers (scaled by 10).

        Args:
            api_value: Temperature value from API

        Returns:
            Corrected temperature value
        """
        raw_value = int(api_value * 10)
        # Convert to signed 16-bit using Python's built-in byte conversion
        unsigned_value = raw_value & 0xFFFF
        bytes_data = ComfoClimeAPI.signed_int_to_bytes(unsigned_value, 2)
        signed_value = ComfoClimeAPI.bytes_to_signed_int(bytes_data)
        return signed_value / 10.0

    async def async_get_uuid(self, hass):
        async with self._request_lock:
            return await hass.async_add_executor_job(self.get_uuid)

    def get_uuid(self):
        response = requests.get(f"{self.base_url}/monitoring/ping", timeout=5)
        response.raise_for_status()
        data = response.json()
        self.uuid = data.get("uuid")
        return self.uuid

    async def async_get_dashboard_data(self, hass):
        async with self._request_lock:
            return await hass.async_add_executor_job(self.get_dashboard_data)

    def get_dashboard_data(self):
        if not self.uuid:
            self.get_uuid()
        response = requests.get(
            f"{self.base_url}/system/{self.uuid}/dashboard", timeout=5
        )
        response.raise_for_status()
        data = response.json()

        for key, val in data.items():
            if "Temperature" in key:
                data[key] = self.fix_signed_temperature(data[key])
        return data

    async def async_get_connected_devices(self, hass):
        async with self._request_lock:
            return await hass.async_add_executor_job(self.get_connected_devices)

    def get_connected_devices(self):
        if not self.uuid:
            self.get_uuid()
        url = f"{self.base_url}/system/{self.uuid}/devices"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json().get("devices", [])

    async def async_read_telemetry_for_device(
        self, hass, device_uuid, telemetry_id, faktor=1.0, signed=True, byte_count=None
    ):
        async with self._request_lock:
            return await hass.async_add_executor_job(
                self.read_telemetry_for_device,
                device_uuid,
                telemetry_id,
                faktor,
                signed,
                byte_count,
            )

    def read_telemetry_for_device(
        self, device_uuid, telemetry_id, faktor=1.0, signed=True, byte_count=None
    ):
        url = f"{self.base_url}/device/{device_uuid}/telemetry/{telemetry_id}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        payload = response.json()

        data = payload.get("data")
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("Unerwartetes Telemetrie-Format")

        value = self.bytes_to_signed_int(data, byte_count, signed)

        if self.entry.options.get("throttle_comfonet", False):
            time.sleep(0.01)
        return value * faktor

    async def async_read_property_for_device(
        self,
        hass,
        device_uuid: str,
        property_path: str,
        faktor: float = 1.0,
        signed: bool = True,
        byte_count: int | None = None,
    ):
        async with self._request_lock:
            return await hass.async_add_executor_job(
                self.read_property_for_device,
                device_uuid,
                property_path,
                faktor,
                signed,
                byte_count,
            )

    def read_property_for_device_raw(
        self, device_uuid: str, property_path: str
    ) -> None | list:
        url = f"{self.base_url}/device/{device_uuid}/property/{property_path}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            _LOGGER.exception(f"Fehler beim Abrufen der Property {property_path}")
            return None

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Unerwartetes Property-Format")
        if self.entry.options.get("throttle_comfonet", False):
            time.sleep(0.01)
        return data

    def read_property_for_device(
        self,
        device_uuid: str,
        property_path: str,
        faktor: float = 1.0,
        signed: bool = True,
        byte_count: int | None = None,
    ) -> None | str | float:
        data = self.read_property_for_device_raw(device_uuid, property_path)

        # Wenn data leer/None ist, können wir nicht fortfahren
        if not data:
            return None

        if byte_count in (1, 2):
            value = self.bytes_to_signed_int(data, byte_count, signed)
        elif byte_count > 2:
            if len(data) != byte_count:
                raise ValueError(
                    f"Unerwartete Byte-Anzahl: erwartet {byte_count}, erhalten {len(data)}"
                )
            if all(0 <= byte < 256 for byte in data):
                return "".join(chr(byte) for byte in data if byte != 0)
        else:
            raise ValueError(f"Nicht unterstützte Byte-Anzahl: {byte_count}")

        return value * faktor

    async def async_get_thermal_profile(self, hass):
        async with self._request_lock:
            return await hass.async_add_executor_job(self.get_thermal_profile)

    def get_thermal_profile(self):
        if not self.uuid:
            self.get_uuid()
        url = f"{self.base_url}/system/{self.uuid}/thermalprofile"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            _LOGGER.warning(f"Fehler beim Abrufen von thermal_profile: {e}")
            return {}  # leer zurückgeben statt crashen

    def update_thermal_profile(self, updates: dict):
        """
        updates: dict mit Teilwerten, z. B. {"heatingThermalProfileSeasonData": {"comfortTemperature": 20.0}}

        Diese Methode füllt alle anderen Felder mit None (null), wie von der API gefordert.
        """
        full_payload = {
            "season": {
                "status": None,
                "season": None,
                "heatingThresholdTemperature": None,
                "coolingThresholdTemperature": None,
            },
            "temperature": {
                "status": None,
                "manualTemperature": None,
            },
            "temperatureProfile": None,
            "heatingThermalProfileSeasonData": {
                "comfortTemperature": None,
                "kneePointTemperature": None,
                "reductionDeltaTemperature": None,
            },
            "coolingThermalProfileSeasonData": {
                "comfortTemperature": None,
                "kneePointTemperature": None,
                "temperatureLimit": None,
            },
        }

        # Deep-Update: überschreibe gezielt Felder im Payload
        for section, values in updates.items():
            if section in full_payload and isinstance(values, dict):
                full_payload[section].update(values)
            else:
                full_payload[section] = values  # z. B. "temperatureProfile": 1

        if not self.uuid:
            self.get_uuid()

        url = f"{self.base_url}/system/{self.uuid}/thermalprofile"
        response = requests.put(url, json=full_payload, timeout=5)
        response.raise_for_status()
        return response.status_code == 200

    def update_dashboard(
        self,
        set_point_temperature: float | None = None,
        fan_speed: int | None = None,
        season: int | None = None,
        hp_standby: bool | None = None,
        schedule: int | None = None,
        temperature_profile: int | None = None,
        season_profile: int | None = None,
        status: int | None = None,
        scenario: int | None = None,
        scenario_time_left: int | None = None,
        scenario_start_delay: int | None = None,
    ) -> dict:
        """Update dashboard settings via API.

        Modern method for dashboard updates. Only fields that are provided
        (not None) will be included in the update payload.

        # Android app export from @msfuture
        payload = {
            "@type": None,
            "name": None,
            "displayName": None,
            "description": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": status,
            "setPointTemperature": set_point_temperature,
            "temperatureProfile": temperature_profile,
            "seasonProfile": season_profile,
            "fanSpeed": fan_speed,
            "scenario": None,
            "scenarioTimeLeft": None,
            "season": season,
            "schedule": None,
            "scenarioStartDelay": None
        }

        The API distinguishes between two modes:
        - Automatic mode (status=1): Uses preset profiles (seasonProfile, temperatureProfile)
        - Manual mode (status=0): Uses manual temperature (setPointTemperature)

        Scenario modes:
        - 4: Kochen (Cooking) - 30 minutes high ventilation
        - 5: Party - 30 minutes high ventilation
        - 7: Urlaub (Holiday) - 24 hours reduced mode
        - 8: Boost - 30 minutes maximum power

        Args:
            set_point_temperature: Target temperature (°C) - activates manual mode
            fan_speed: Fan speed (0-3)
            season: Season value (0=transition, 1=heating, 2=cooling)
            hp_standby: Heat pump standby state (True=standby/off, False=active)
            schedule: Schedule mode
            temperature_profile: Temperature profile/preset (0=comfort, 1=boost, 2=eco)
            season_profile: Season profile/preset (0=comfort, 1=boost, 2=eco)
            status: Temperature control mode (0=manual, 1=automatic)
            scenario: Scenario mode (4=Kochen, 5=Party, 7=Urlaub, 8=Boost)
            scenario_time_left: Duration for scenario in seconds (e.g., 1800 for 30min)
            scenario_start_delay: Start delay for scenario in seconds (optional)

        Returns:
            Response JSON from the API

        Raises:
            requests.RequestException: If the API request fails
        """
        if not self.uuid:
            self.get_uuid()

        # Dynamically build payload; only include keys explicitly provided.
        # payload: dict = {}
        payload: dict = {
            "@type": None,
            "name": None,
            "displayName": None,
            "description": None,
            "timestamp": None,
            "status": status,
            "setPointTemperature": set_point_temperature,
            "temperatureProfile": temperature_profile,
            "seasonProfile": season_profile,
            "fanSpeed": fan_speed,
            "scenario": None,
            "scenarioTimeLeft": None,
            "season": season,
            "schedule": None,
        }
        if set_point_temperature is not None:
            payload["setPointTemperature"] = set_point_temperature
        if fan_speed is not None:
            payload["fanSpeed"] = fan_speed
        if season is not None:
            payload["season"] = season
        if schedule is not None:
            payload["schedule"] = schedule
        if temperature_profile is not None:
            payload["temperatureProfile"] = temperature_profile
        if season_profile is not None:
            payload["seasonProfile"] = season_profile
        if status is not None:
            payload["status"] = status
        if hp_standby is not None:
            payload["hpStandby"] = hp_standby
        if scenario is not None:
            payload["scenario"] = scenario
        if scenario_time_left is not None:
            payload["scenarioTimeLeft"] = scenario_time_left
        if scenario_start_delay is not None:
            payload["scenarioStartDelay"] = scenario_start_delay

        if not payload:
            _LOGGER.debug(
                "No dashboard fields to update (empty payload) - skipping PUT"
            )
            return {}

        # Add timestamp to payload
        tz = ZoneInfo(self.hass.config.time_zone)
        payload["timestamp"] = datetime.now(tz).isoformat()

        headers = {"content-type": "application/json; charset=utf-8"}
        url = f"{self.base_url}/system/{self.uuid}/dashboard"
        try:
            response = requests.put(url, json=payload, timeout=5, headers=headers)
            response.raise_for_status()
            try:
                resp_json = response.json()
            except Exception:
                resp_json = {"text": response.text}
            _LOGGER.debug(f"Dashboard update OK payload={payload} response={resp_json}")
        except Exception:
            _LOGGER.exception(f"Error updating dashboard (payload={payload})")
            raise
        return resp_json

    async def async_update_dashboard(self, hass, **kwargs):
        """Async wrapper for update_dashboard method."""
        async with self._request_lock:
            return await hass.async_add_executor_job(
                lambda: self.update_dashboard(**kwargs)
            )

    async def async_update_thermal_profile(self, hass, updates: dict):
        """Async wrapper for update_thermal_profile method."""
        async with self._request_lock:
            return await hass.async_add_executor_job(
                lambda: self.update_thermal_profile(updates)
            )

    async def async_set_hvac_season(self, hass, season: int, hp_standby: bool = False):
        """Set HVAC season and standby state in a single atomic operation.

        This method updates both the season (via thermal profile) and hpStandby
        (via dashboard) in a single lock to prevent race conditions.

        Args:
            hass: Home Assistant instance
            season: Season value (0=transition, 1=heating, 2=cooling)
            hp_standby: Heat pump standby state (False=active, True=standby/off)
        """
        async with self._request_lock:

            def _update():
                # First update dashboard to set hpStandby
                self.update_dashboard(hp_standby=hp_standby)
                # Then update thermal profile to set season
                if not hp_standby:  # Only set season if device is active
                    self.update_thermal_profile({"season": {"season": season}})

            return await hass.async_add_executor_job(_update)

    async def async_set_property_for_device(
        self,
        hass,
        device_uuid: str,
        property_path: str,
        value: float,
        *,
        byte_count: int,
        signed: bool = True,
        faktor: float = 1.0,
    ):
        async with self._request_lock:
            return await hass.async_add_executor_job(
                lambda: self.set_property_for_device(
                    device_uuid,
                    property_path,
                    value,
                    byte_count=byte_count,
                    signed=signed,
                    faktor=faktor,
                )
            )

    def set_property_for_device(
        self,
        device_uuid: str,
        property_path: str,
        value: float,
        *,
        byte_count: int,
        signed: bool = True,
        faktor: float = 1.0,
    ):
        if byte_count not in (1, 2):
            raise ValueError("Nur 1 oder 2 Byte unterstützt")

        raw_value = int(round(value / faktor))
        data = self.signed_int_to_bytes(raw_value, byte_count, signed)

        x, y, z = map(int, property_path.split("/"))
        url = f"{self.base_url}/device/{device_uuid}/method/{x}/{y}/3"
        payload = {"data": [z] + data}

        try:
            response = requests.put(url, json=payload, timeout=5)
            response.raise_for_status()
        except Exception:
            _LOGGER.exception(
                f"Fehler beim Schreiben von Property {property_path} mit Payload {payload}"
            )
            raise

    async def async_reset_system(self, hass):
        async with self._request_lock:
            return await hass.async_add_executor_job(self.reset_system)

    def reset_system(self):
        """Trigger a restart of the ComfoClime device."""
        url = f"{self.base_url}/system/reset"
        response = requests.put(url, timeout=5)
        response.raise_for_status()
        return response.status_code == 200
