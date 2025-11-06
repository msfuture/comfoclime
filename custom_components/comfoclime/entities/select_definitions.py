SELECT_ENTITIES = [
    {
        "key": "temperatureProfile",
        "name": "Temperature Profile",
        "translation_key": "temperature_profile",
        "options": {0: "comfort", 1: "power", 2: "eco"},
    },
    {
        "key": "season.season",
        "name": "Season Mode",
        "translation_key": "season_mode",
        "options": {1: "heating", 0: "transitional", 2: "cooling"},
    },
]

PROPERTY_SELECT_ENTITIES = {
    1: [
        {
            "path": "29/1/6",
            "name": "Humidity Comfort Control",
            "translation_key": "humidity_comfort_control",
            "options": {0: "off", 1: "autoonly", 2: "on"},
        },
        {
            "path": "29/1/7",  # X/Y/Z
            "name": "Humidity Protection",
            "translation_key": "humidity_protection",
            "options": {0: "off", 1: "autoonly", 2: "on"},
        },
    ]
}
