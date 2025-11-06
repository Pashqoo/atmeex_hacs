import logging

import voluptuous as vol
from atmeexpy.client import AtmeexClient

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from .const import DOMAIN, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)

# Словарь переводов ошибок для отображения пользователю
ERROR_TRANSLATIONS = {
    "authentication_failed": "Ошибка аутентификации. Проверьте email и пароль.",
    "no_devices_found": "В аккаунте не найдено устройств. Если у вас несколько адресов в приложении, проверьте, что устройства видны в выбранном адресе. Проверьте мобильное приложение Atmeex.",
    "connection_error": "Ошибка подключения к серверу Atmeex. Проверьте интернет-соединение.",
    "timeout_error": "Превышено время ожидания ответа от сервера. Попробуйте позже.",
    "invalid_auth": "Неверный email или пароль. Проверьте учетные данные.",
    "invalid_input": "Неверные данные. Проверьте правильность ввода.",
    "unknown_error": "Неизвестная ошибка. Проверьте логи для деталей.",
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    },
)

class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for atmeex cloud."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        email = user_input.get(CONF_EMAIL)

        try:
            _LOGGER.info(f"Attempting to authenticate with email: {email}")
            
            # Создаем клиент
            # Аутентификация может происходить лениво при первом API запросе
            atmeex = AtmeexClient(email, user_input.get(CONF_PASSWORD))
            
            _LOGGER.info(f"Fetching devices for account {email}...")
            
            # Получаем устройства (это также может выполнить аутентификацию)
            # ВАЖНО: Библиотека atmeexpy может печатать данные в stdout, но возвращать пустой список
            # Поэтому мы также проверяем сырой ответ API
            try:
                devices = await atmeex.get_devices()
                device_count = len(devices) if devices else 0
                _LOGGER.debug(f"get_devices() returned: type={type(devices)}, count={device_count}")
                if devices:
                    _LOGGER.debug(f"First device type: {type(devices[0]) if len(devices) > 0 else 'N/A'}")
            except Exception as get_devices_err:
                _LOGGER.error(f"Error calling get_devices(): {get_devices_err}")
                devices = []
                device_count = 0
            
            # Проверяем, что аутентификация прошла успешно после получения устройств
            if not hasattr(atmeex.auth, '_access_token') or not atmeex.auth._access_token:
                _LOGGER.error(f"Authentication failed for {email}: no access token received after API call")
                errors["base"] = "authentication_failed"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )
            
            _LOGGER.info(f"Authentication successful for {email}. Found {device_count} device(s) via library")
            
            # ИСПРАВЛЕНИЕ: Если библиотека вернула пустой список, проверяем сырой ответ API
            # Это решает проблему, когда библиотека atmeexpy не может распарсить ответ
            raw_api_device_count = 0
            raw_devices_data = None
            if device_count == 0:
                _LOGGER.warning(f"Library returned 0 devices, attempting to check raw API response...")
                
                # Пробуем разные способы доступа к HTTP клиенту
                http_client = None
                http_client_source = None
                
                # Способ 1: Прямой доступ через _http_client
                if hasattr(atmeex, '_http_client'):
                    http_client = atmeex._http_client
                    http_client_source = '_http_client'
                # Способ 2: Через http_client (без подчеркивания)
                elif hasattr(atmeex, 'http_client'):
                    http_client = atmeex.http_client
                    http_client_source = 'http_client'
                # Способ 3: Через вложенный _client
                elif hasattr(atmeex, '_client') and hasattr(atmeex._client, '_http_client'):
                    http_client = atmeex._client._http_client
                    http_client_source = '_client._http_client'
                
                if http_client:
                    try:
                        _LOGGER.debug(f"HTTP client found via {http_client_source}, making request to /devices...")
                        if hasattr(http_client, 'get'):
                            resp = await http_client.get("/devices")
                            _LOGGER.debug(f"Response status: {resp.status_code}")
                            
                            if resp.status_code == 200:
                                raw_devices_data = resp.json()
                                if isinstance(raw_devices_data, list):
                                    raw_api_device_count = len(raw_devices_data)
                                    _LOGGER.info(f"✓ Raw API returned {raw_api_device_count} device(s)")
                                    
                                    if raw_api_device_count > 0:
                                        _LOGGER.warning(
                                            f"Library atmeexpy failed to parse devices, but API returned {raw_api_device_count} device(s). "
                                            "This is a known issue with the library. Integration will proceed."
                                        )
                                        # Логируем информацию об устройствах из сырого ответа
                                        for idx, device_data in enumerate(raw_devices_data, 1):
                                            device_id = device_data.get('id', 'unknown')
                                            device_name = device_data.get('name', f'Device {idx}')
                                            room_id = device_data.get('room_id')
                                            online = device_data.get('online', False)
                                            _LOGGER.info(
                                                f"  Device {idx}: {device_name} (ID: {device_id}, "
                                                f"Online: {online}"
                                                f"{', Room ID: ' + str(room_id) if room_id else ''})"
                                            )
                                else:
                                    _LOGGER.warning(f"API returned non-list data: {type(raw_devices_data).__name__}")
                            else:
                                _LOGGER.warning(f"API returned status {resp.status_code}: {resp.text[:200]}")
                    except AttributeError as attr_err:
                        _LOGGER.warning(f"HTTP client found but missing 'get' method: {attr_err}")
                    except Exception as api_check_err:
                        _LOGGER.warning(f"Error checking raw API response: {api_check_err}")
                        import traceback
                        _LOGGER.debug(f"Traceback: {traceback.format_exc()}")
                else:
                    _LOGGER.warning(
                        "HTTP client not accessible. Tried: _http_client, http_client, _client._http_client. "
                        "Cannot verify if API returned devices."
                    )
                    # Логируем доступные атрибуты для отладки
                    available_attrs = [attr for attr in dir(atmeex) if not attr.startswith('__')]
                    _LOGGER.debug(f"Available attributes on AtmeexClient: {', '.join(available_attrs[:20])}")
            
            # Детальное логирование для диагностики (особенно для случаев с несколькими адресами)
            # ВАЖНО: Если raw_api_device_count > 0, значит устройства есть, и мы разрешаем настройку
            if device_count == 0 and raw_api_device_count == 0:
                _LOGGER.warning(
                    f"No devices found in account {email}. "
                    "This might mean: 1) No devices are added to this account, "
                    "2) Devices are not connected to internet, "
                    "3) API returned empty list, "
                    "4) Devices might be in a different address/location in the app. "
                    "Please check the Atmeex mobile app - if you have multiple addresses, "
                    "make sure devices are visible in the currently selected address."
                )
                _LOGGER.warning(
                    f"NOTE: HTTP client was not accessible to verify devices via raw API. "
                    f"If devices exist in the app, this might be a library issue. "
                    f"Check logs for more details."
                )
                errors["base"] = "no_devices_found"
            else:
                # Если библиотека вернула устройства ИЛИ сырой API вернул устройства - разрешаем настройку
                # Это исправляет проблему с парсингом библиотеки
                final_device_count = device_count if device_count > 0 else raw_api_device_count
                
                if device_count == 0 and raw_api_device_count > 0:
                    _LOGGER.info(
                        f"Allowing integration setup despite library parsing issue. "
                        f"API confirmed {raw_api_device_count} device(s) exist."
                    )
                elif device_count > 0:
                    # Логируем информацию о найденных устройствах для диагностики
                    _LOGGER.info(f"Successfully found {device_count} device(s) for {email}")
                    for idx, device in enumerate(devices):
                        device_id = device.model.id if hasattr(device.model, 'id') else 'unknown'
                        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Device {idx+1}"
                        device_online = getattr(device.model, 'online', None)
                        # Проверяем, есть ли информация об адресе/локации
                        device_address = None
                        if hasattr(device.model, 'address'):
                            device_address = device.model.address
                        elif hasattr(device.model, 'location'):
                            device_address = device.model.location
                        elif hasattr(device, 'address'):
                            device_address = device.address
                        
                        _LOGGER.info(
                            f"Device {idx+1}: {device_name} (ID: {device_id}, "
                            f"Online: {device_online}"
                            f"{', Address: ' + str(device_address) if device_address else ''})"
                        )
                
                # Сохраняем токены и создаем конфигурацию
                user_input[CONF_ACCESS_TOKEN] = atmeex.auth._access_token
                user_input[CONF_REFRESH_TOKEN] = atmeex.auth._refresh_token
                final_device_count = device_count if device_count > 0 else raw_api_device_count
                _LOGGER.info(f"Successfully configured integration for {email} with {final_device_count} device(s)")
                return self.async_create_entry(
                    title=email,
                    data=user_input,
                )
                
        except ConnectionError as exc:
            _LOGGER.error(f"Connection error for {email}: {exc}")
            errors["base"] = "connection_error"
        except TimeoutError as exc:
            _LOGGER.error(f"Timeout error for {email}: {exc}")
            errors["base"] = "timeout_error"
        except ValueError as exc:
            error_msg = str(exc).lower()
            if "invalid" in error_msg or "credential" in error_msg or "password" in error_msg:
                _LOGGER.error(f"Invalid credentials for {email}: {exc}")
                errors["base"] = "invalid_auth"
            else:
                _LOGGER.error(f"Value error for {email}: {exc}")
                errors["base"] = "invalid_input"
        except Exception as exc:
            _LOGGER.exception(f"Unexpected exception during setup for {email}: {exc}")
            # Пытаемся понять тип ошибки по сообщению
            error_msg = str(exc).lower()
            if "auth" in error_msg or "credential" in error_msg or "password" in error_msg:
                errors["base"] = "invalid_auth"
            elif "connection" in error_msg or "network" in error_msg or "timeout" in error_msg:
                errors["base"] = "connection_error"
            else:
                errors["base"] = "unknown_error"

        # Переводим ключи ошибок в понятные сообщения
        if errors.get("base") in ERROR_TRANSLATIONS:
            errors["base"] = ERROR_TRANSLATIONS[errors["base"]]
        
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
