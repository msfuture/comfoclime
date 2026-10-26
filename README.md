# comfoclime

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

HomeAssistant integration of Zehnder ComfoClime (and all devices in ComfoNet bus like the ComfoAir Q)

## Features
ComfoClime is a HVAC solution as additional device for the ComfoAir Q series. It comes with its own app and an propietary JSON API. The ComfoClime unit is connected to the local network via WiFi/WLAN, the API is available only local via HTTP requests without authentication. The integration can also control the ventilation main unit ComfoAir Q. It currently offers:

* reading the dashboard data similar to the official app
* climate control entity with HVAC modes (heat/cool/fan_only/off), temperature profiles and scenarios
* reading and writing the active temperature profile and comfort settings
* setting the ventilation fan speed
* temporary ComfoAir Q ventilation presets (Away, Low, Medium, High and Boost) with automatic return to the schedule
* temporary ComfoAir Q bypass control (on/off, or automatic)
* temporary Cooking, Party, Holiday and Boost scenarios
* ComfoAir Q filter days remaining and reported alarm codes
* ComfoAir Q passive-cooling availability from ComfoClime firmware 1.5.5+
* autodiscovering all connected devices
* property (r/w) and telemetry (r/o) values of *all* connected devices
* restarting the ComfoClime unit via service call
* configuration via config flow by host/ip
* translations in English and German

## Installation
* add this fork via HACS (user defined repositories, URL: `https://github.com/eilandnl/comfoclime`)
* install the "Zehnder ComfoClime" integration in HACS
* restart Home Assistant
* add the ComfoClime device (connected devices like the ComfoAir Q are detected and added automatically)

## API Documentation

API documentation with practical Python examples:

* **[ComfoClimeAPI.md](ComfoClimeAPI.md)** - Concise API reference with Python code examples
* **[Original documentation](https://github.com/msfuture/comfoclime_api/blob/main/ComfoClimeAPI.md)** - Detailed reverse engineered API knowledge
* **[PDO Protocol](https://github.com/michaelarnauts/aiocomfoconnect/blob/master/docs/PROTOCOL-PDO.md)** - Telemetry sensor protocol
* **[RMI Protocol](https://github.com/michaelarnauts/aiocomfoconnect/blob/master/docs/PROTOCOL-RMI.md)** - Property access protocol

Feel free to extend!

## Climate Control Features

The integration provides a comprehensive climate control entity that unifies all temperature and ventilation control features:

### HVAC Modes
- **Off**: System standby mode
- **Heat**: Heating mode (automatically sets season to heating)
- **Cool**: Cooling mode (automatically sets season to cooling)
- **Fan Only**: Ventilation only mode (season set to transition)

Additionally there are controls for the fan speed of the connected ComfoAir Q device. The range goes from 0 to 3.

### Temporary scenarios

The ComfoClime climate entity supports the Cooking, Party, Holiday and Boost
scenarios as preset modes. You can also call `comfoclime.set_scenario_mode`.
The service accepts an optional duration in minutes (1–1440); defaults are
30 minutes for Cooking, Party and Boost, and 24 hours for Holiday. These
scenario identifiers and defaults follow the still-open upstream proposal and
have not been verified against every ComfoClime firmware version.

### ComfoAir Q bypass

Use `comfoclime.set_bypass_mode` to temporarily set the connected ComfoAir Q
bypass to `on` or `off`, or select `auto` to cancel the override and return to
the unit's automatic control. The optional duration is in minutes (1–1440)
and defaults to 60 minutes. Timed overrides expire automatically.

### Timed ComfoAir Q ventilation presets

Use `comfoclime.set_ventilation_mode` to run `away`, `low`, `medium`, `high` or
`boost` for a chosen duration (1–1440 minutes). Select `auto` to cancel the
ComfoAir Q preset timers and resume its normal schedule. The integration also
exposes the remaining filter life and the raw non-zero alarm codes reported by
each connected device. Alarm codes are not decoded into Zehnder descriptions.

The dashboard's `Passive Cooling Available` binary sensor reflects the
`caqFreeCoolingAvailable` field, which the ComfoClime API documents for
firmware 1.5.5 and newer.

### Temperature Profiles and Preset Modes
- **Comfort**: Maximum comfort temperature profile
- **Eco**: Energy efficient temperature profile
- **Boost, Cooking, Party and Holiday**: Temporary ComfoClime scenarios

### Temperature Control
- Set target temperature for heating (15-25°C) and cooling (20-28°C) seasons
- Current temperature display from indoor sensor
- Automatic temperature range adjustment based on active season

### Smart Season Detection
The climate entity automatically:
- Detects current season from ComfoClime dashboard
- Adjusts available temperature ranges accordingly
- Shows appropriate HVAC actions (heating/cooling/fan/idle)
- Manages system state based on fan activity

## Caveats

With some firmware versions, the ComfoClimeAPI stops being responsive after a few days. Pressing "Reset" on the Arduino board or power cycling the device will fix it. An alternative solution is to set up an automation that restarts the ComfoNet board daily: 

```yaml
alias: Reset ComfoClome Daily
description: ''
triggers:
  - trigger: time
    at: '22:00:00'
conditions: []
actions:
  - action: comfoclime.reset_system
    metadata: {}
    data: {}
mode: single
```

For details, see https://github.com/msfuture/comfoclime/issues/7.

## Device coverage
Available controls and telemetry depend on the connected device model and firmware. The integration exposes the ComfoClime climate controls and selected ComfoAir Q ventilation, bypass, alarm and filter data; it does not decode every ComfoNet property or alarm code. Validate additional device properties against the target model and firmware before relying on them.

Feel free to participate! 🙋‍♂️

## Thanks to...

@michaelarnauts and his integration of ComfoConnect, where I discovered a lot of telemetries and properties of the ventilation unit:
https://github.com/michaelarnauts/aiocomfoconnect
