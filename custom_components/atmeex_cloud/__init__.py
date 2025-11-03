from datetime import timedelta
import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from atmeexpy.client import AtmeexClient

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Создаем AtmeexClient в отдельном потоке, чтобы избежать блокирующих вызовов в event loop
    def _create_client():
        return AtmeexClient(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    
    api = await hass.async_add_executor_job(_create_client)
    api.restore_tokens(entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_REFRESH_TOKEN])

    coordinator = AtmeexDataCoordinator(hass, api, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_refresh()

    # Исправлено: используем async_forward_entry_setups вместо устаревшего async_forward_entry_setup
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

class AtmeexDataCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, api: AtmeexClient, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name="Atmeex Coordinator",
            update_interval=timedelta(seconds=60),
        )

        self.hass = hass
        self.api = api
        self.devices = []
        self.entry: ConfigEntry = entry

    async def _async_update_data(self):
        self.devices = await self.api.get_devices()
        
        # Логируем информацию о полученных устройствах для отладки
        _LOGGER.debug(f"Received {len(self.devices)} devices from API")
        
        # Пробуем обновить данные каждого устройства отдельно, чтобы получить condition
        for device in self.devices:
            device_id = device.model.id
            device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Device {device_id}"
            
            # Если condition отсутствует, пробуем получить его через отдельный запрос
            if device.model.condition is None:
                _LOGGER.debug(f"Device {device_name} (ID: {device_id}): condition is None, trying to fetch condition data")
                try:
                    # Пробуем получить condition через API напрямую
                    # Возможно, нужно сделать отдельный запрос GET /devices/{id}/condition
                    if hasattr(self.api, '_http_client'):
                        _LOGGER.debug(f"Trying to fetch condition for device {device_id} via direct API call")
                        try:
                            # Пробуем получить данные устройства через GET /devices/{id}
                            resp = await self.api._http_client.get(f"/devices/{device_id}")
                            if resp.status_code == 200:
                                device_data = resp.json()
                                # Проверяем, есть ли condition в ответе
                                if 'condition' in device_data and device_data['condition']:
                                    from atmeexpy.device import DeviceConditionModel
                                    device.model.condition = DeviceConditionModel.fromdict(device_data['condition'])
                                    _LOGGER.info(f"Successfully fetched condition for device {device_name} (ID: {device_id})")
                                else:
                                    _LOGGER.debug(f"No condition in device data for {device_id}")
                        except Exception as api_err:
                            _LOGGER.debug(f"Could not fetch condition via API for device {device_id}: {api_err}")
                    
                    # Также пробуем методы объекта device
                    if device.model.condition is None and (hasattr(device, 'refresh') or hasattr(device, 'update') or hasattr(device, 'get_info')):
                        _LOGGER.debug(f"Trying to refresh device {device_id} data via device methods")
                        if hasattr(device, 'refresh'):
                            await device.refresh()
                        elif hasattr(device, 'update'):
                            await device.update()
                        elif hasattr(device, 'get_info'):
                            await device.get_info()
                except Exception as e:
                    _LOGGER.debug(f"Could not refresh device {device_id} data: {e}")
            
            has_condition = device.model.condition is not None
            
            if has_condition:
                # Получаем все доступные атрибуты condition
                condition_attrs = {}
                if hasattr(device.model.condition, '__dict__'):
                    condition_attrs = device.model.condition.__dict__
                elif hasattr(device.model.condition, '__annotations__'):
                    # Если это dataclass, пробуем получить все поля
                    for attr_name in device.model.condition.__annotations__:
                        condition_attrs[attr_name] = getattr(device.model.condition, attr_name, 'N/A')
                else:
                    # Пробуем получить атрибуты через dir
                    for attr_name in dir(device.model.condition):
                        if not attr_name.startswith('_'):
                            try:
                                condition_attrs[attr_name] = getattr(device.model.condition, attr_name, 'N/A')
                            except:
                                pass
                
                # Логируем все поля condition
                _LOGGER.info(f"Device {device_name} (ID: {device_id}) condition FULL DATA: {condition_attrs}")
                
                # Также логируем специфические поля
                condition_info = {
                    'co2_ppm': getattr(device.model.condition, 'co2_ppm', None),
                    'temp_room': getattr(device.model.condition, 'temp_room', None),
                    'temp_in': getattr(device.model.condition, 'temp_in', None),
                    'hum_room': getattr(device.model.condition, 'hum_room', None),
                }
                _LOGGER.debug(f"Device {device_name} (ID: {device_id}) condition specific fields: {condition_info}")
            else:
                # Логируем полную структуру device.model для диагностики
                device_model_attrs = {}
                if hasattr(device.model, '__dict__'):
                    device_model_attrs = {k: v for k, v in device.model.__dict__.items() if k != 'condition'}
                elif hasattr(device.model, '__annotations__'):
                    # Если это dataclass, пробуем получить все поля
                    for attr_name in device.model.__annotations__:
                        if attr_name != 'condition':
                            try:
                                device_model_attrs[attr_name] = getattr(device.model, attr_name, 'N/A')
                            except:
                                pass
                else:
                    # Пробуем получить атрибуты через dir
                    for attr_name in dir(device.model):
                        if not attr_name.startswith('_') and attr_name != 'condition':
                            try:
                                device_model_attrs[attr_name] = getattr(device.model, attr_name, 'N/A')
                            except:
                                pass
                
                # Логируем на уровне INFO для лучшей видимости
                _LOGGER.info(f"Device {device_name} (ID: {device_id}) model structure (without condition): {device_model_attrs}")
                
                # Логируем важные статусы для диагностики
                online_status = getattr(device.model, 'online', None)
                pwr_on_status = getattr(device.model.settings, 'u_pwr_on', None) if hasattr(device.model, 'settings') else None
                
                _LOGGER.warning(
                    f"Device {device_name} (ID: {device_id}): condition is None - CO2, Temperature, Humidity sensors will show 'Unknown'. "
                    f"Device online: {online_status}, Power on: {pwr_on_status}. "
                    f"Condition may only be available when device is online and powered on."
                )

        if self.entry.data[CONF_ACCESS_TOKEN] != self.api.auth._access_token or \
            self.entry.data[CONF_REFRESH_TOKEN] != self.api.auth._refresh_token:

            # Исправлено: используем copy() чтобы избежать изменения неизменяемого словаря
            data = self.entry.data.copy()
            data[CONF_ACCESS_TOKEN] = self.api.auth._access_token
            data[CONF_REFRESH_TOKEN] = self.api.auth._refresh_token

            await self.hass.config_entries.async_update_entry(self.entry, data=data)
