DASHBOARD_SENSORS = [
    {
        "key": "indoorTemperature",
        "name": "Indoor Temperature",
        "translation_key": "indoor_temperature",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "key": "outdoorTemperature",
        "name": "Outdoor Temperature",
        "translation_key": "outdoor_temperature",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    {
        "key": "exhaustAirFlow",
        "name": "Exhaust Air Flow",
        "translation_key": "exhaust_air_flow",
        "unit": "m³/h",
        "state_class": "measurement",
        "device_class": "volume_flow_rate",
    },
    {
        "key": "supplyAirFlow",
        "name": "Supply Air Flow",
        "translation_key": "supply_air_flow",
        "unit": "m³/h",
        "state_class": "measurement",
        "device_class": "volume_flow_rate",
    },
    {
        "key": "fanSpeed",
        "name": "Fan Speed",
        "translation_key": "fan_speed",
    },
    {
        "key": "temperatureProfile",
        "name": "Temperature Profile Status",
        "translation_key": "temperature_profile_status",
    },
    {
        "key": "season",
        "name": "Season",
        "translation_key": "season",
    },
    {
        "key": "schedule",
        "name": "Schedule",
        "translation_key": "schedule_status",
    },
    {
        "key": "status",
        "name": "Status",
        "translation_key": "dashboard_status",
    },
    {
        "key": "heatPumpStatus",
        "name": "Heat Pump Status",
        "translation_key": "heat_pump_status",
    },
    {
        "key": "hpStandby",
        "name": "Device Power Status",
        "translation_key": "device_power_status",
    },
    {
        "key": "freeCoolingEnabled",
        "name": "Free Cooling Status",
        "translation_key": "free_cooling_status",
    },
]

TELEMETRY_SENSORS = []

CONNECTED_DEVICE_SENSORS = {
    20: [
        {
            "telemetry_id": 4193,
            "name": "Supply Air Temperature",
            "translation_key": "supply_air_temperature",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 4145,
            "name": "TPMA Temperature",
            "translation_key": "tpma_temperature",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 4149,
            "name": "Device Mode",
            "translation_key": "device_mode_status",
            "faktor": 1,
        },
        {
            "telemetry_id": 4151,
            "name": "Current Comfort Temperature",
            "translation_key": "current_comfort_temperature",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 4194,
            "name": "Unknown temp 4194",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4195,
            "name": "Unknown temp 4195",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4196,
            "name": "Unknown temp 4196",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4197,
            "name": "Unknown temp 4197",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4198,
            "name": "Unknown value 4198",
            "byte_count": 1,
            "diagnose": True,
        },
        {
            "telemetry_id": 4201,
            "name": "Power Heatpump",
            "translation_key": "power_heatpump",
            "unit": "W",
            "device_class": "power",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 4202,
            "name": "Unknown value 4202",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4203,
            "name": "Unknown value 4203",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4204,
            "name": "Unknown value 4204",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4205,
            "name": "Unknown value 4205",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4206,
            "name": "Unknown value 4206",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4207,
            "name": "Unknown value 4207",
            "state_class": "measurement",
            "diagnose": True,
        },
        {
            "telemetry_id": 4208,
            "name": "Unknown value 4208",
            "state_class": "measurement",
            "diagnose": True,
        },
    ],
    1: [
        {
            "telemetry_id": 117,
            "name": "Exhaust Fan Duty",
            "translation_key": "exhaust_fan_duty",
            "unit": "%",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 118,
            "name": "Supply Fan Duty",
            "translation_key": "supply_fan_duty",
            "unit": "%",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 121,
            "name": "Exhaust Fan Speed",
            "translation_key": "exhaust_fan_speed",
            "unit": "rpm",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 122,
            "name": "Supply Fan Speed",
            "translation_key": "supply_fan_speed",
            "unit": "rpm",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 128,
            "name": "Power Ventilation",
            "translation_key": "power_ventilation",
            "unit": "W",
            "device_class": "power",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 129,
            "name": "Energy YTD",
            "translation_key": "energy_ytd",
            "unit": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
        {
            "telemetry_id": 130,
            "name": "Energy Total",
            "translation_key": "energy_total",
            "unit": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
        {
            "telemetry_id": 209,
            "name": "Mean outdoor temperature (RMOT)",
            "translation_key": "temp_rmot",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 227,
            "name": "Bypass State",
            "translation_key": "bypass_state",
            "unit": "%",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 275,
            "name": "Exhaust Temperature",
            "translation_key": "exhaust_temperature",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 278,
            "name": "Supply Temperature",
            "translation_key": "supply_air_temperature",
            "unit": "°C",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
            "device_class": "temperature",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 290,
            "name": "Extract Humidity",
            "translation_key": "extract_humidity",
            "unit": "%",
            "device_class": "humidity",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 291,
            "name": "Exhaust Humidity",
            "translation_key": "exhaust_humidity",
            "unit": "%",
            "device_class": "humidity",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 292,
            "name": "Outdoor Humidity",
            "translation_key": "outdoor_humidity",
            "unit": "%",
            "device_class": "humidity",
            "state_class": "measurement",
        },
        {
            "telemetry_id": 294,
            "name": "Supply Humidity",
            "translation_key": "supply_humidity",
            "unit": "%",
            "device_class": "humidity",
            "state_class": "measurement",
        },
    ],
}

CONNECTED_DEVICE_PROPERTIES = {
    1: [
        {
            "path": "30/1/18",  # X/Y/Z
            "name": "Ventilation Disbalance",
            "translation_key": "ventilation_disbalance",
            "unit": "%",
            "faktor": 0.1,
            "signed": True,
            "byte_count": 2,
        },
    ],
}
