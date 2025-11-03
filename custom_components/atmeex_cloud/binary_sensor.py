import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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

    entities = []
    for device in coordinator.devices:
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        
        # Индикатор отсутствия воды удален - зависит от condition, который недоступен через REST API
        # Доступен только когда устройство онлайн через WebSocket
        
        # Статус онлайн (доступен всегда из model.online)
        entities.append(AtmeexOnlineBinarySensor(device, coordinator, device_name))
    
    async_add_entities(entities)

class AtmeexOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for online status."""
    
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = 'mdi:access-point-network'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_online"
        self._attr_name = f"{device_name} Online"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    def _handle_coordinator_update(self) -> None:
        device_id = self.device.model.id
        same_devices = [d for d in self.coordinator.devices if d.model.id == device_id]
        
        if len(same_devices) == 0:
            self._attr_available = False
        else:
            self.device = same_devices[0]
            self._update_state()
        
        self.async_write_ha_state()
    
    def _update_state(self) -> None:
        # online может быть None, обрабатываем это
        self._attr_is_on = self.device.model.online is True
        self._attr_available = True

