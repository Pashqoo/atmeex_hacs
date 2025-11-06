import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from atmeexpy.device import Device
from atmeexpy.device import DeviceSettingsSetModel

from . import AtmeexDataCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    device_count = len(coordinator.devices) if coordinator.devices else 0
    _LOGGER.info(f"Setting up fan entities for {device_count} device(s)")
    
    if device_count == 0:
        _LOGGER.warning("No devices in coordinator when setting up fan entities. Entities will be empty.")
    
    entities = [AtmeexFanEntity(device, coordinator) for device in coordinator.devices]
    _LOGGER.info(f"Creating {len(entities)} fan entities")
    async_add_entities(entities)

class AtmeexFanEntity(CoordinatorEntity, FanEntity):
    
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_percentage: int | None = None
    _attr_is_on: bool = False
    
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
        )
        
        self._update_state()
    
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(f"Turning on fan {self.name}")
        
        # Включаем устройство если выключено
        if not self.device.model.settings.u_pwr_on:
            await self.device.set_power(True)
        
        # Если указана скорость, устанавливаем её
        if percentage is not None:
            # Конвертируем процент (0-100) в скорость вентилятора (0-6)
            # Например: 0-14% = 0, 15-28% = 1, ... 85-100% = 6
            speed = min(6, max(0, round(percentage / 16.67)))
            await self.device.set_fan_speed(speed)
        
        # Переключаем в режим вентиляции (FAN_ONLY)
        try:
            await self.device.set_heat_temp(-1000)
        except ValueError:
            # Если библиотека не принимает -1000, используем прямой доступ к API
            await self.device._set_params(DeviceSettingsSetModel(u_temp_room=-1000))
        
        await self.coordinator.async_request_refresh()
    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        _LOGGER.debug(f"Turning off fan {self.name}")
        await self.device.set_power(False)
        await self.coordinator.async_request_refresh()
    
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        
        # Конвертируем процент (0-100) в скорость вентилятора (0-6)
        speed = min(6, max(0, round(percentage / 16.67)))
        await self.device.set_fan_speed(speed)
        
        # Если устройство выключено, включаем его
        if not self.device.model.settings.u_pwr_on:
            await self.device.set_power(True)
        
        await self.coordinator.async_request_refresh()
    
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device_id = self.device.model.id
        same_devices = [d for d in self.coordinator.devices if d.model.id == device_id]
        
        if len(same_devices) == 0:
            self._attr_available = False
        else:
            self.device = same_devices[0]
            self._update_state()
        
        self.async_write_ha_state()
    
    def _update_state(self) -> None:
        """Update the state of the fan entity."""
        # Обновляем состояние вентилятора
        is_on = self.device.model.settings.u_pwr_on and \
                self.device.model.settings.u_temp_room == -1000
        
        # Конвертируем скорость вентилятора (0-6) в процент (0-100)
        fan_speed = self.device.model.settings.u_fan_speed
        self._attr_percentage = int((fan_speed + 1) * 16.67) if is_on else 0
        self._attr_is_on = is_on