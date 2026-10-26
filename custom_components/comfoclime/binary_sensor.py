from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import ComfoClimeDashboardCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up dashboard-backed ComfoClime binary sensors."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    main_device = entry_data.get("main_device")
    if main_device is None:
        return

    async_add_entities(
        [
            ComfoClimeCoolingAvailableBinarySensor(
                entry, entry_data["coordinator"], main_device
            )
        ]
    )


class ComfoClimeCoolingAvailableBinarySensor(
    CoordinatorEntity[ComfoClimeDashboardCoordinator], BinarySensorEntity
):
    """Expose ComfoAir Q support for passive cooling as a binary sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_cooling_available"

    def __init__(self, entry: ConfigEntry, coordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_config_entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_dashboard_caqFreeCoolingAvailable"

    @property
    def is_on(self) -> bool | None:
        """Return whether the connected ComfoAir Q can provide passive cooling."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get("caqFreeCoolingAvailable")
        return value if isinstance(value, bool) else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device["uuid"])},
            name=self._device.get("displayName", "ComfoClime"),
            manufacturer="Zehnder",
            model=self._device.get("@modelType"),
            sw_version=self._device.get("version"),
        )
