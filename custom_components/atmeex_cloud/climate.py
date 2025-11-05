import logging

from homeassistant.components.climate import ClimateEntity, HVACMode, ClimateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from atmeexpy.device import Device
from atmeexpy.device import DeviceSettingsSetModel

from . import AtmeexDataCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    coordinator: AtmeexDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([AtmeexClimateEntity(device, coordinator) for device in coordinator.devices])

class AtmeexClimateEntity(CoordinatorEntity, ClimateEntity):

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.FAN_ONLY]  # Убрали OFF - управление через switch
    _attr_min_temp = 10
    _attr_max_temp = 30
    _attr_fan_modes = ["1", "2", "3", "4", "5", "6", "7"]
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    _attr_icon = 'mdi:air-purifier'
    _attr_fan_mode: int


    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)

        self.coordinator = coordinator
        self.device = device
        
        # Уникальный ID для entity (позволяет настраивать через UI)
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_climate"
        # Имя устройства из API или дефолтное
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        self._attr_name = device_name
        
        # Информация об устройстве для группировки entities
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )

        self._update_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set hvac mode."""
        _LOGGER.info("Need to set mode to %s, current mode is %s", hvac_mode, self.hvac_mode)
        
        # Проверяем, что устройство включено
        if not self.device.model.settings.u_pwr_on:
            _LOGGER.warning(f"Cannot set HVAC mode when device is off. Please turn on the device first using the power switch.")
            return
        
        if self.hvac_mode == hvac_mode:
            # Do nothing if mode is same
            _LOGGER.debug(f"{self.name} is asked for mode {hvac_mode}, but it is already in {self.hvac_mode}. Do "
                          f"nothing.")
            return
        
        if hvac_mode == HVACMode.HEAT:
            saved_target_temp = self.target_temperature
            
            # Если температура не установлена (None), используем значение по умолчанию (22°C)
            if saved_target_temp is None:
                saved_target_temp = 22.0
                _LOGGER.debug(f"{self.name}: target_temperature was None, using default 22°C")
            
            # Убеждаемся, что температура в допустимых пределах (10-30°C)
            saved_target_temp = max(self._attr_min_temp, min(self._attr_max_temp, saved_target_temp))

            # Конвертация: API использует температуру * 10 (100-300 вместо 10-30)
            api_temp = int(saved_target_temp * 10)
            await self.device.set_heat_temp(api_temp)
            
            # Обновляем target_temperature после установки
            self._attr_target_temperature = saved_target_temp
        elif hvac_mode == HVACMode.FAN_ONLY:
            # Для режима вентиляции используем специальное значение -1000 (HEATER_DISABLE_TEMP)
            # Обрабатываем возможную ошибку валидации в библиотеке
            try:
                await self.device.set_heat_temp(-1000)
            except ValueError as e:
                # Если библиотека не принимает -1000, используем прямой доступ к API
                if "not between 100 and 300" in str(e):
                    _LOGGER.debug(f"Library validation failed for -1000, using direct API call: {e}")
                    # Используем прямой доступ к API через _set_params (обход валидации)
                    await self.device._set_params(DeviceSettingsSetModel(u_temp_room=-1000))
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return

        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str):
        """Set fan speed."""
        # Проверяем, что устройство включено
        if not self.device.model.settings.u_pwr_on:
            _LOGGER.warning(f"Cannot set fan speed when device is off. Please turn on the device first using the power switch.")
            return
        await self.device.set_fan_speed(int(fan_mode)-1)

    async def async_set_temperature(self, **kwargs):
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Проверяем, что устройство включено
        if not self.device.model.settings.u_pwr_on:
            _LOGGER.warning(f"Cannot set temperature when device is off. Please turn on the device first using the power switch.")
            return
        
        # Конвертация: API использует температуру * 10 (100-300 вместо 10-30)
        api_temp = int(temperature * 10)
        await self.device.set_heat_temp(api_temp)

    async def async_turn_on(self):
        """Turn on climate entity - устанавливает дефолтный режим приточной вентиляции."""
        # Если устройство выключено, включаем его через switch
        if not self.device.model.settings.u_pwr_on:
            # Устанавливаем режим приточной вентиляции по умолчанию
            await self.device._set_params(DeviceSettingsSetModel(
                u_pwr_on=True,
                u_damp_pos=0,  # Заслонка открыта
                u_fan_speed=1 if self.device.model.settings.u_fan_speed == 0 else self.device.model.settings.u_fan_speed
            ))
        # Если устройство уже включено, устанавливаем режим приточной вентиляции
        else:
            await self.device._set_params(DeviceSettingsSetModel(
                u_damp_pos=0  # Режим приточной вентиляции
            ))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Turn off climate entity - выключает устройство через switch."""
        _LOGGER.debug(f"Turning off from {self.hvac_mode}")
        await self.device._set_params(DeviceSettingsSetModel(
            u_pwr_on=False,
            u_damp_pos=2  # Закрываем заслонку при выключении
        ))
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

    def _update_state(self):
        """Update climate entity state."""
        # Если устройство выключено, показываем FAN_ONLY (но управление через switch)
        if not self.device.model.settings.u_pwr_on:
            self._attr_hvac_mode = HVACMode.FAN_ONLY
            self._attr_fan_mode = "1"  # Дефолтная скорость
            self._attr_target_temperature = None
            self._attr_available = False  # Делаем недоступным для управления
            return
        
        self._attr_available = True
        self._attr_fan_mode = str(self.device.model.settings.u_fan_speed+1)
        
        # Конвертация: API возвращает температуру * 10, нужно разделить на 10
        # Также проверяем на HEATER_DISABLE_TEMP (-1000) для режима FAN_ONLY
        api_temp = self.device.model.settings.u_temp_room
        if api_temp == -1000:  # HEATER_DISABLE_TEMP для режима вентиляции
            self._attr_target_temperature = None
            self._attr_hvac_mode = HVACMode.FAN_ONLY
        elif api_temp > 0:
            self._attr_target_temperature = api_temp / 10.0
            self._attr_hvac_mode = HVACMode.HEAT
        else:
            # Если температура не установлена, по умолчанию FAN_ONLY
            self._attr_target_temperature = None
            self._attr_hvac_mode = HVACMode.FAN_ONLY

