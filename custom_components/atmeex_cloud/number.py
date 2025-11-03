import logging

from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from atmeexpy.device import Device
from atmeexpy.device import DeviceSettingsSetModel

from . import AtmeexDataCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AtmeexHumidityTargetNumberEntity(device, coordinator) for device in coordinator.devices])

class AtmeexHumidityTargetNumberEntity(CoordinatorEntity, NumberEntity):
    """Number entity for target humidity control."""
    
    _attr_device_class = NumberDeviceClass.HUMIDITY
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = 'mdi:water-percent'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_humidity_target"
        self._attr_name = f"{device_name} Humidity Target"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the target humidity value."""
        _LOGGER.debug(f"Setting target humidity to {value}% for {self.name}")
        
        humidity_value = int(value)
        
        # Ограничиваем диапазон
        humidity_value = max(0, min(100, humidity_value))
        
        await self.device._set_params(DeviceSettingsSetModel(u_hum_stg=humidity_value))
        await self.coordinator.async_request_refresh()
    
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
        self._attr_native_value = float(self.device.model.settings.u_hum_stg)
        self._attr_available = True

