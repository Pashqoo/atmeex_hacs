import logging

from homeassistant.components.switch import SwitchEntity
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
        
        entities.append(AtmeexAutoModeSwitch(device, coordinator, device_name))
        entities.append(AtmeexNightModeSwitch(device, coordinator, device_name))
        entities.append(AtmeexCoolModeSwitch(device, coordinator, device_name))
    
    async_add_entities(entities)

class BaseAtmeexSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Atmeex switches."""
    
    async def _set_custom_param(self, param_name: str, value):
        """Set custom parameter directly via HTTP."""
        # Используем HTTP клиент из API клиента, который уже настроен правильно
        try:
            # Получаем HTTP клиент из API клиента
            http_client = self.coordinator.api._http_client
            base_url = getattr(self.coordinator.api, '_base_url', 'https://api.atmeex.ru')
            
            # Используем относительный путь, клиент сам добавит base_url
            resp = await http_client.put(
                f"/devices/{self.device.model.id}/params",
                json={param_name: value}
            )
            resp.raise_for_status()
            
            # Обновляем модель устройства из ответа
            device_info = resp.json()
            from atmeexpy.device import DeviceModel
            self.device.model = DeviceModel.fromdict(device_info)
        except AttributeError:
            # Если HTTP клиент недоступен напрямую, используем device._set_params через расширенную модель
            # Но DeviceSettingsSetModel не поддерживает эти параметры, поэтому делаем прямой PUT
            try:
                # Пытаемся использовать HTTP клиент через device
                if hasattr(self.device, '_http_client'):
                    resp = await self.device._http_client.put(
                        f"/devices/{self.device.model.id}/params",
                        json={param_name: value}
                    )
                    resp.raise_for_status()
                    device_info = resp.json()
                    from atmeexpy.device import DeviceModel
                    self.device.model = DeviceModel.fromdict(device_info)
                else:
                    raise
            except Exception as e2:
                _LOGGER.error(f"Error setting {param_name} to {value}: {e2}")
                raise
        except Exception as e:
            _LOGGER.error(f"Error setting {param_name} to {value}: {e}")
            raise

class AtmeexAutoModeSwitch(BaseAtmeexSwitch):
    """Switch for automatic mode."""
    
    _attr_icon = 'mdi:auto-fix'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_auto_mode"
        self._attr_name = f"{device_name} Auto Mode"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on automatic mode."""
        _LOGGER.debug(f"Enabling auto mode for {self.name}")
        await self._set_custom_param("u_auto", True)
        await self.coordinator.async_request_refresh()
    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off automatic mode."""
        _LOGGER.debug(f"Disabling auto mode for {self.name}")
        await self._set_custom_param("u_auto", False)
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
        self._attr_is_on = self.device.model.settings.u_auto
        self._attr_available = True

class AtmeexNightModeSwitch(BaseAtmeexSwitch):
    """Switch for night mode."""
    
    _attr_icon = 'mdi:moon-waxing-crescent'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_night_mode"
        self._attr_name = f"{device_name} Night Mode"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on night mode."""
        _LOGGER.debug(f"Enabling night mode for {self.name}")
        await self._set_custom_param("u_night", True)
        await self.coordinator.async_request_refresh()
    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off night mode."""
        _LOGGER.debug(f"Disabling night mode for {self.name}")
        await self._set_custom_param("u_night", False)
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
        self._attr_is_on = self.device.model.settings.u_night
        self._attr_available = True

class AtmeexCoolModeSwitch(BaseAtmeexSwitch):
    """Switch for cool mode."""
    
    _attr_icon = 'mdi:snowflake'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_cool_mode"
        self._attr_name = f"{device_name} Cool Mode"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on cool mode."""
        _LOGGER.debug(f"Enabling cool mode for {self.name}")
        await self._set_custom_param("u_cool_mode", True)
        await self.coordinator.async_request_refresh()
    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off cool mode."""
        _LOGGER.debug(f"Disabling cool mode for {self.name}")
        await self._set_custom_param("u_cool_mode", False)
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
        self._attr_is_on = self.device.model.settings.u_cool_mode
        self._attr_available = True

