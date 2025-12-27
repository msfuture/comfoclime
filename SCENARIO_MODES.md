# Szenario-Modi für ComfoClime Climate Entity

## Übersicht

Die ComfoClime Integration unterstützt jetzt Szenario-Modi als Preset-Optionen in der Climate Entity. Diese Modi ermöglichen zeitlich begrenzte Betriebsmodi für spezielle Situationen.

## Verfügbare Szenario-Modi

| Szenario    | Preset Name | Wert | Standard-Dauer       | Beschreibung                             |
| ----------- | ----------- | ---- | -------------------- | ---------------------------------------- |
| 🍳 Kochen   | `cooking` | 4    | 30 Minuten           | Hohe Lüftung für Kochaktivitäten      |
| 🎉 Party    | `party`   | 5    | 30 Minuten           | Hohe Lüftung für Gäste                |
| 🏖️ Urlaub | `away`    | 7    | 24 Stunden (1440min) | Reduzierter Betrieb während Abwesenheit |
| ⚡ Boost    | `boost`   | 8    | 30 Minuten           | Maximale Leistung                        |

## Verwendung

### Via Home Assistant UI

1. Öffne die Climate Entity (z.B. `climate.comfoclime`)
2. Wähle einen Szenario-Modus aus dem Preset-Dropdown
3. Der Modus wird mit der Standard-Dauer aktiviert

### Via Service Call

#### Methode 1: Standard Climate Service (Standard-Dauer)

```yaml
service: climate.set_preset_mode
target:
  entity_id: climate.comfoclime
data:
  preset_mode: cooking
```

#### Methode 2: Custom Service (mit benutzerdefinierter Dauer)

```yaml
service: comfoclime.set_scenario_mode
data:
  entity_id: climate.comfoclime
  scenario: cooking
  duration: 60  # Dauer in Minuten, z.B. 60 für 1 Stunde
```



## Restzeit-Anzeige

Die verbleibende Zeit des aktiven Szenarios wird als Attribut der Climate Entity angezeigt:

```yaml
# Attribute der Climate Entity:
scenario_time_left: 1798  # in Sekunden
scenario_time_left_formatted: "29m 58s"  # lesbares Format
```

### Template Sensor für Restzeit

```yaml
template:
  - sensor:
      - name: "ComfoClime Szenario Restzeit"
        state: >
          {{ state_attr('climate.comfoclime', 'scenario_time_left_formatted') | default('Kein aktives Szenario') }}
        icon: mdi:timer-outline
```

## Dashboard-Integration

### Beispiel Lovelace Card

```yaml
type: entities
title: ComfoClime Steuerung
entities:
  - entity: climate.comfoclime
    type: climate
  - type: attribute
    entity: climate.comfoclime
    attribute: scenario_time_left_formatted
    name: Szenario Restzeit
    icon: mdi:timer-outline
```

### Button Card für schnellen Zugriff

```yaml
type: horizontal-stack
cards:
  - type: button
    name: Kochen
    icon: mdi:pot-steam
    tap_action:
      action: call-service
      service: climate.set_preset_mode
      service_data:
        entity_id: climate.comfoclime
        preset_mode: cooking
  - type: button
    name: Party
    icon: mdi:party-popper
    tap_action:
      action: call-service
      service: climate.set_preset_mode
      service_data:
        entity_id: climate.comfoclime
        preset_mode: party
  - type: button
    name: Urlaub
    icon: mdi:beach
    tap_action:
      action: call-service
      service: climate.set_preset_mode
      service_data:
        entity_id: climate.comfoclime
        preset_mode: away
  - type: button
    name: Boost
    icon: mdi:rocket-launch
    tap_action:
      action: call-service
      service: climate.set_preset_mode
      service_data:
        entity_id: climate.comfoclime
        preset_mode: boost
```

## API Details

### Dashboard API Parameter

Beim Aktivieren eines Szenarios werden folgende Parameter an die Dashboard API gesendet:

```python
{
    "scenario": 4,              # Szenario-Wert (4, 5, 7, oder 8)
    "scenarioTimeLeft": 1800,   # Dauer (API-Parameter in Sekunden; wird im Code aus Minuten * 60 berechnet, Benutzer geben die Dauer in Minuten an)
    "timestamp": "YYYY-MM-DDTHH:MM:SSZ"
}
```

### Standard-Dauern (in Code definiert)

```python
SCENARIO_DEFAULT_DURATIONS = {
    4: 30,   # Kochen: 30 Minuten
    5: 30,   # Party: 30 Minuten
    7: 1440,  # Urlaub: 24 Stunden
    8: 30,   # Boost: 30 Minuten
}
```

## Hinweise

- ⏱️ Die Restzeit wird automatisch vom Gerät heruntergezählt
- 🔄 Ein aktives Szenario kann jederzeit durch ein anderes Preset überschrieben werden
- 🛑 Um ein Szenario vorzeitig zu beenden, wähle ein anderes Preset (z.B. "Komfort")
- 📊 Die Restzeit wird über die Dashboard API abgerufen und alle 30 Sekunden aktualisiert

## Troubleshooting

### Szenario wird nicht aktiviert

1. Prüfe die Logs: `Settings -> System -> Logs -> Custom Component: comfoclime`
2. Stelle sicher, dass die Climate Entity verfügbar ist
3. Überprüfe die Netzwerkverbindung zum ComfoClime-Gerät

### Restzeit wird nicht angezeigt

Die Restzeit wird als Attribut der Climate Entity bereitgestellt. Stelle sicher, dass:

- Die Dashboard-Daten erfolgreich abgerufen werden
- Der Coordinator läuft (Update-Intervall: 30 Sekunden)

### Benutzerdefinierte Dauer funktioniert nicht

Verwende den `comfoclime.set_scenario_mode` Service statt `climate.set_preset_mode` für benutzerdefinierte Dauern.
