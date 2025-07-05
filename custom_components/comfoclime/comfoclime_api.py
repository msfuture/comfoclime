# comfoclime_api.py
import asyncio
import datetime
import logging

import requests

_LOGGER = logging.getLogger(__name__)


class ComfoClimeAPI:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.uuid = None
        self._request_lock = asyncio.Lock()

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
        return response.json()

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

        if byte_count is None:
            byte_count = len(data)

        if byte_count == 1:
            value = data[0]
            if signed and value >= 0x80:
                value -= 0x100
        elif byte_count == 2:
            lsb, msb = data[:2]
            value = lsb + (msb << 8)
            if signed and value >= 0x8000:
                value -= 0x10000
        else:
            raise ValueError(f"Nicht unterstützte Byte-Anzahl: {byte_count}")

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
        self,
        device_uuid: str,
        property_path: str
    ) -> None | list:
        url = f"{self.base_url}/device/{device_uuid}/property/{property_path}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            _LOGGER.error(f"Fehler beim Abrufen der Property {property_path}: {e}")
            return None

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise ValueError("Unerwartetes Property-Format")
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
        if byte_count is None and data:
            byte_count = len(data)
        else:
            return None

        if byte_count == 1:
            value = data[0]
            if signed and value >= 0x80:
                value -= 0x100
        elif byte_count == 2:
            lsb, msb = data[:2]
            value = lsb + (msb << 8)
            if signed and value >= 0x8000:
                value -= 0x10000
        elif byte_count > 2:
            if len(data) != byte_count:
                raise ValueError(f"Unerwartete Byte-Anzahl: erwartet {byte_count}, erhalten {len(data)}")
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

    def set_device_setting(self, temperature_profile=None, fan_speed=None):
        if not self.uuid:
            self.get_uuid()
        payload = {
            "@type": None,
            "name": None,
            "displayName": None,
            "description": None,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": None,
            "setPointTemperature": None,
            "temperatureProfile": temperature_profile,
            "seasonProfile": None,
            "fanSpeed": fan_speed,
            "scenario": None,
            "scenarioTimeLeft": None,
            "season": None,
            "schedule": None,
        }
        headers = {"content-type": "application/json; charset=utf-8"}
        url = f"{self.base_url}/system/{self.uuid}/dashboard"
        try:
            response = requests.put(url, json=payload, timeout=5, headers=headers)
            response.raise_for_status()
        except Exception as e:
            _LOGGER.error(f"Fehler beim Schreiben der Geräteeinstellung: {e}")
            raise

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

        # Wert zurückrechnen, falls ein Faktor verwendet wird
        raw_value = int(round(value / faktor))

        # Bytes erzeugen
        if byte_count == 1:
            if signed and raw_value < 0:
                raw_value += 0x100
            data = [raw_value & 0xFF]
        elif byte_count == 2:
            if signed and raw_value < 0:
                raw_value += 0x10000
            data = [raw_value & 0xFF, (raw_value >> 8) & 0xFF]

        x, y, z = map(int, property_path.split("/"))
        url = f"{self.base_url}/device/{device_uuid}/method/{x}/{y}/3"
        payload = {"data": [z] + data}

        try:
            response = requests.put(url, json=payload, timeout=5)
            response.raise_for_status()
        except Exception as e:
            _LOGGER.error(
                f"Fehler beim Schreiben von Property {property_path} mit Payload {payload}: {e}"
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
