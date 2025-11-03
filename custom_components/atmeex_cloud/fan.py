import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from atmeexpy.device import Device

from . import AtmeexDataCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AtmeexFanEntity(device, coordinator) for device in coordinator.devices])

class AtmeexFanEntity(CoordinatorEntity, FanEntity):
    
    _attr_supported_features = FanEntityFeature.SET_SPEED
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        # Уникальный ID для entity (позволяет настраивать через UI)
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_fan"
        # Имя устройства из API или дефолтное
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        self._attr_name = f"{device_name} Fan"
        
        # Информация об устройстве для группировки entities (тот же идентификатор, что и у climate)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
            via_device=(DOMAIN, coordinator.entry.entry_id),
        )