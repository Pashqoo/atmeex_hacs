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
            devices = await atmeex.get_devices()
            device_count = len(devices) if devices else 0
            
            # Проверяем, что аутентификация прошла успешно после получения устройств
            if not hasattr(atmeex.auth, '_access_token') or not atmeex.auth._access_token:
                _LOGGER.error(f"Authentication failed for {email}: no access token received after API call")
                errors["base"] = "authentication_failed"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )
            
            _LOGGER.info(f"Authentication successful for {email}. Found {device_count} device(s)")
            
            # Детальное логирование для диагностики (особенно для случаев с несколькими адресами)
            if device_count == 0:
                _LOGGER.warning(
                    f"No devices found in account {email}. "
                    "This might mean: 1) No devices are added to this account, "
                    "2) Devices are not connected to internet, "
                    "3) API returned empty list, "
                    "4) Devices might be in a different address/location in the app. "
                    "Please check the Atmeex mobile app - if you have multiple addresses, "
                    "make sure devices are visible in the currently selected address."
                )
                # Попробуем получить больше информации через прямой API запрос
                try:
                    if hasattr(atmeex, '_http_client'):
                        _LOGGER.debug(f"Attempting direct API call to /devices to get more information")
                        resp = await atmeex._http_client.get("/devices")
                        if resp.status_code == 200:
                            devices_data = resp.json()
                            _LOGGER.debug(f"Direct API response: {devices_data}")
                            _LOGGER.info(f"API returned {len(devices_data) if isinstance(devices_data, list) else 'non-list'} devices")
                        else:
                            _LOGGER.warning(f"API returned status code {resp.status_code}: {resp.text}")
                except Exception as api_debug_err:
                    _LOGGER.debug(f"Could not get additional API info: {api_debug_err}")
                
                errors["base"] = "no_devices_found"
            else:
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
                _LOGGER.info(f"Successfully configured integration for {email} with {device_count} device(s)")
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
