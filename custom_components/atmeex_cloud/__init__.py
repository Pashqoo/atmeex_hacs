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
        device_count = len(self.devices) if self.devices else 0
        
        # Логируем информацию о полученных устройствах для отладки
        _LOGGER.debug(f"Received {device_count} devices from API via library")
        
        # ИСПРАВЛЕНИЕ: Если библиотека вернула пустой список, проверяем сырой ответ API
        # Это решает проблему, когда библиотека atmeexpy не может распарсить ответ
        if device_count == 0:
            _LOGGER.warning("Library returned 0 devices, checking raw API response in coordinator...")
            
            # Пробуем разные способы доступа к HTTP клиенту
            http_client = None
            if hasattr(self.api, '_http_client'):
                http_client = self.api._http_client
            elif hasattr(self.api, 'http_client'):
                http_client = self.api.http_client
            elif hasattr(self.api, '_client') and hasattr(self.api._client, '_http_client'):
                http_client = self.api._client._http_client
            
            if http_client and hasattr(http_client, 'get'):
                try:
                    resp = await http_client.get("/devices")
                    if resp.status_code == 200:
                        raw_devices_data = resp.json()
                        if isinstance(raw_devices_data, list) and len(raw_devices_data) > 0:
                            _LOGGER.warning(
                                f"Library atmeexpy failed to parse devices in coordinator, "
                                f"but API returned {len(raw_devices_data)} device(s). "
                                f"Attempting to create Device objects from raw data..."
                            )
                            
                            # Пробуем создать объекты Device из сырых данных
                            try:
                                from atmeexpy.device import Device, DeviceModel
                                
                                parsed_devices = []
                                for device_data in raw_devices_data:
                                    try:
                                        # Создаем DeviceModel из словаря
                                        device_model = DeviceModel.fromdict(device_data)
                                        # Создаем Device объект
                                        device = Device(device_model, self.api)
                                        parsed_devices.append(device)
                                        _LOGGER.info(
                                            f"Successfully parsed device: {device_data.get('name', 'Unknown')} "
                                            f"(ID: {device_data.get('id')})"
                                        )
                                    except Exception as parse_err:
                                        _LOGGER.warning(
                                            f"Failed to parse device {device_data.get('id', 'unknown')}: {parse_err}"
                                        )
                                
                                if parsed_devices:
                                    self.devices = parsed_devices
                                    _LOGGER.info(
                                        f"Successfully created {len(parsed_devices)} device(s) from raw API data"
                                    )
                                else:
                                    _LOGGER.warning("Failed to parse any devices from raw API data")
                            except ImportError as import_err:
                                _LOGGER.error(f"Failed to import Device/DeviceModel: {import_err}")
                            except Exception as parse_all_err:
                                _LOGGER.error(f"Failed to parse devices from raw data: {parse_all_err}")
                except Exception as api_err:
                    _LOGGER.debug(f"Could not check raw API response in coordinator: {api_err}")
            else:
                _LOGGER.debug("HTTP client not accessible in coordinator for raw API check")
        
        # Пробуем обновить данные каждого устройства отдельно, чтобы получить condition
        for device in self.devices:
            device_id = device.model.id
            device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Device {device_id}"
            
            # Если condition отсутствует, пробуем получить его через отдельный запрос
            # Даже если устройство показывает online: False, condition может быть доступен
            if device.model.condition is None:
                _LOGGER.debug(f"Device {device_name} (ID: {device_id}): condition is None, trying to fetch condition data")
                try:
                    # Пробуем получить condition через API напрямую
                    # Возможно, нужно сделать отдельный запрос GET /devices/{id} или GET /devices/{id}/condition
                    if hasattr(self.api, '_http_client'):
                        _LOGGER.debug(f"Trying to fetch condition for device {device_id} via direct API call")
                        try:
                            # Пробуем получить данные устройства через GET /devices/{id}
                            resp = await self.api._http_client.get(f"/devices/{device_id}")
                            if resp.status_code == 200:
                                device_data = resp.json()
                                _LOGGER.debug(f"Device {device_id} API response: {device_data}")
                                
                                # Проверяем, есть ли condition в ответе
                                if 'condition' in device_data and device_data['condition']:
                                    from atmeexpy.device import DeviceConditionModel
                                    device.model.condition = DeviceConditionModel.fromdict(device_data['condition'])
                                    _LOGGER.info(f"Successfully fetched condition for device {device_name} (ID: {device_id})")
                                elif 'condition' in device_data and device_data['condition'] is None:
                                    _LOGGER.debug(f"Device {device_id} has condition field but it's None in API response")
                                else:
                                    _LOGGER.debug(f"No condition field in device data for {device_id}")
                                    
                                # Также обновляем статус online если он изменился
                                if 'online' in device_data:
                                    device.model.online = device_data['online']
                                    _LOGGER.debug(f"Updated online status for device {device_id}: {device_data['online']}")
                        except Exception as api_err:
                            _LOGGER.warning(f"Could not fetch condition via API for device {device_id}: {api_err}")
                    
                    # Также пробуем методы объекта device
                    if device.model.condition is None and (hasattr(device, 'refresh') or hasattr(device, 'update') or hasattr(device, 'get_info')):
                        _LOGGER.debug(f"Trying to refresh device {device_id} data via device methods")
                        try:
                            if hasattr(device, 'refresh'):
                                await device.refresh()
                            elif hasattr(device, 'update'):
                                await device.update()
                            elif hasattr(device, 'get_info'):
                                await device.get_info()
                        except Exception as device_err:
                            _LOGGER.debug(f"Device method refresh failed for {device_id}: {device_err}")
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
                
                # Логируем важные статусы для диагностики
                online_status = getattr(device.model, 'online', None)
                pwr_on_status = getattr(device.model.settings, 'u_pwr_on', None) if hasattr(device.model, 'settings') else None
                
                # Логируем полную структуру на уровне WARNING для лучшей видимости
                _LOGGER.warning(
                    f"Device {device_name} (ID: {device_id}): condition is None. "
                    f"Device online: {online_status}, Power on: {pwr_on_status}. "
                    f"Full model data: {device_model_attrs}"
                )
                _LOGGER.warning(
                    f"Device {device_name} (ID: {device_id}): CO2, Temperature, Humidity sensors will show 'Unknown'. "
                    f"Condition is only available when device is online. Please check device connectivity in Atmeex mobile app."
                )

        if self.entry.data[CONF_ACCESS_TOKEN] != self.api.auth._access_token or \
            self.entry.data[CONF_REFRESH_TOKEN] != self.api.auth._refresh_token:

            # Исправлено: используем copy() чтобы избежать изменения неизменяемого словаря
            data = self.entry.data.copy()
            data[CONF_ACCESS_TOKEN] = self.api.auth._access_token
            data[CONF_REFRESH_TOKEN] = self.api.auth._refresh_token

            # Исправлено: async_update_entry должен быть async функцией
            # Но в некоторых случаях может возвращать bool (баг или старая версия HA)
            # Используем безопасный способ обновления
            try:
                # Проверяем, является ли метод async функцией
                update_method = self.hass.config_entries.async_update_entry
                if asyncio.iscoroutinefunction(update_method):
                    await update_method(self.entry, data=data)
                else:
                    # Если это не async функция, вызываем напрямую
                    # Это не должно происходить, но обрабатываем для совместимости
                    _LOGGER.debug("async_update_entry is not a coroutine function, calling directly")
                    update_method(self.entry, data=data)
            except TypeError as e:
                # Если возникает ошибка "object bool can't be used in 'await' expression"
                # это означает, что метод вернул bool вместо coroutine
                _LOGGER.warning(
                    f"async_update_entry returned non-coroutine (likely bool). "
                    f"This might be a Home Assistant version issue. Error: {e}. "
                    f"Skipping entry update - tokens will be updated on next successful update."
                )
                # Не обновляем entry, чтобы избежать ошибки
                # Токены будут обновлены при следующем успешном обновлении
