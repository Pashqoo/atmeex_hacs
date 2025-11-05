import logging

from homeassistant.components.select import SelectEntity
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

    async_add_entities([AtmeexVentilationModeSelectEntity(device, coordinator) for device in coordinator.devices])

class AtmeexVentilationModeSelectEntity(CoordinatorEntity, SelectEntity):
    """Select entity for ventilation mode control."""
    
    # 4 режима работы бризера
    _attr_options = [
        "supply_ventilation",      # Режим приточной вентиляции
        "recirculation",           # Режим рециркуляции
        "mixed",                   # Смешанный режим
        "supply_valve"             # Режим приточного клапана
    ]
    
    # Маппинг опций на русские названия для отображения
    _option_translation = {
        "supply_ventilation": "Режим приточной вентиляции",
        "recirculation": "Режим рециркуляции",
        "mixed": "Смешанный режим",
        "supply_valve": "Режим приточного клапана"
    }
    _attr_icon = 'mdi:air-filter'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_ventilation_mode"
        self._attr_name = f"{device_name} Ventilation Mode"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected ventilation mode."""
        _LOGGER.debug(f"Setting ventilation mode to {option} for {self.name}")
        
        # Проверяем, что устройство включено
        if not self.device.model.settings.u_pwr_on:
            _LOGGER.warning(f"Cannot set ventilation mode when device is off. Please turn on the device first.")
            return
        
        # Режимы работы:
        # 1. Режим приточной вентиляции: u_damp_pos=0, вентилятор работает (u_fan_speed > 0), обогрев может работать
        # 2. Режим рециркуляции: u_damp_pos=2, вентилятор работает, обогрев выключен (u_temp_room=-1000)
        # 3. Смешанный режим: u_damp_pos=1, вентилятор работает, обогрев может работать
        # 4. Режим приточного клапана: u_damp_pos=0, вентилятор выключен (u_fan_speed=0), обогрев не работает
        
        current_fan_speed = self.device.model.settings.u_fan_speed
        current_temp = self.device.model.settings.u_temp_room
        
        if option == "supply_ventilation":
            # Режим приточной вентиляции
            # Заслонка открыта, вентилятор работает (если был выключен, включаем минимальную скорость 1)
            fan_speed = current_fan_speed if current_fan_speed > 0 else 1
            await self.device._set_params(DeviceSettingsSetModel(
                u_damp_pos=0,
                u_fan_speed=fan_speed
            ))
        elif option == "recirculation":
            # Режим рециркуляции
            # Заслонка закрыта, вентилятор работает, обогрев выключен
            fan_speed = current_fan_speed if current_fan_speed > 0 else 1
            await self.device._set_params(DeviceSettingsSetModel(
                u_damp_pos=2,
                u_fan_speed=fan_speed,
                u_temp_room=-1000  # Выключить обогрев
            ))
        elif option == "mixed":
            # Смешанный режим
            # Заслонка смешанная, вентилятор работает
            fan_speed = current_fan_speed if current_fan_speed > 0 else 1
            await self.device._set_params(DeviceSettingsSetModel(
                u_damp_pos=1,
                u_fan_speed=fan_speed
            ))
        elif option == "supply_valve":
            # Режим приточного клапана
            # Заслонка открыта, вентилятор выключен, обогрев выключен
            await self.device._set_params(DeviceSettingsSetModel(
                u_damp_pos=0,
                u_fan_speed=0,
                u_temp_room=-1000  # Выключить обогрев
            ))
        else:
            _LOGGER.error(f"Invalid ventilation mode option: {option}")
            return
        
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
        """Определяем текущий режим на основе состояния устройства."""
        # Если устройство выключено, режим недоступен
        if not self.device.model.settings.u_pwr_on:
            self._attr_current_option = None
            self._attr_available = False
            return
        
        damp_pos = self.device.model.settings.u_damp_pos
        fan_speed = self.device.model.settings.u_fan_speed
        temp_room = self.device.model.settings.u_temp_room
        
        # Определяем режим по состоянию:
        if damp_pos == 0 and fan_speed == 0:
            # Режим приточного клапана: заслонка открыта, вентилятор выключен
            self._attr_current_option = "supply_valve"
        elif damp_pos == 2:
            # Режим рециркуляции: заслонка закрыта
            self._attr_current_option = "recirculation"
        elif damp_pos == 1:
            # Смешанный режим: заслонка смешанная
            self._attr_current_option = "mixed"
        elif damp_pos == 0 and fan_speed > 0:
            # Режим приточной вентиляции: заслонка открыта, вентилятор работает
            self._attr_current_option = "supply_ventilation"
        else:
            # По умолчанию - режим приточной вентиляции
            self._attr_current_option = "supply_ventilation"
        
        self._attr_available = True

