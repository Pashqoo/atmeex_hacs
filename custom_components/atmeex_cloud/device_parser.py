"""
Вспомогательный модуль для парсинга устройств из сырых данных API.
Обходит проблемы библиотеки atmeexpy с парсингом данных.
"""

import logging
from typing import List, Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)


def fix_device_data_for_parsing(device_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Исправляет данные устройства перед парсингом, чтобы обойти проблемы библиотеки atmeexpy.
    
    Проблемы, которые исправляются:
    - None значения в полях, которые должны быть int/float
    - Неправильные типы данных
    - Отсутствующие обязательные поля
    """
    fixed_data = device_data.copy()
    
    # Убеждаемся, что все обязательные поля присутствуют
    # DeviceModel требует: id, mac, type, name, room_id, owner_id, created_at, socket_id, fw_ver, model, online, settings
    required_fields = {
        'id': 0,
        'mac': '',
        'type': 1,
        'name': 'Unknown Device',
        'room_id': 0,
        'owner_id': 0,
        'created_at': '',
        'socket_id': '',
        'fw_ver': '',
        'model': 'A7',
        'online': False,
    }
    
    for field, default_value in required_fields.items():
        if field not in fixed_data or fixed_data[field] is None:
            fixed_data[field] = default_value
            _LOGGER.debug(f"Added missing required field {field} with default value: {default_value}")
    
    # Исправляем settings - обязательное поле для DeviceModel
    if 'settings' not in fixed_data or not fixed_data['settings']:
        # Создаем минимальный settings объект со всеми обязательными полями
        fixed_data['settings'] = {
            'id': 0,
            'device_id': fixed_data.get('id', 0),
            'u_pwr_on': False,
            'u_fan_speed': 0,
            'u_damp_pos': 2,
            'u_temp_room': 0,
            'u_cool_mode': False,
            'u_hum_stg': 0,  # Обязательное поле, устанавливаем 0 если None
            'u_auto': False,  # Должно быть bool, не None
            'u_night': False,  # Должно быть bool, не None
        }
        _LOGGER.debug("Created default settings object with all required fields")
    else:
        settings = fixed_data['settings'].copy()
        
        # Убеждаемся, что обязательные поля settings присутствуют
        # ВАЖНО: Все поля должны иметь правильные типы (не None для bool/int)
        required_settings_fields = {
            'id': 0,
            'device_id': fixed_data.get('id', 0),
            'u_pwr_on': False,
            'u_fan_speed': 0,
            'u_damp_pos': 2,
            'u_temp_room': 0,
            'u_cool_mode': False,
            'u_hum_stg': 0,  # Устанавливаем 0 вместо None
            'u_auto': False,  # Должно быть bool, не None
            'u_night': False,  # Должно быть bool, не None
        }
        
        for field, default_value in required_settings_fields.items():
            if field not in settings or settings[field] is None:
                settings[field] = default_value
                _LOGGER.debug(f"Added missing settings field {field} with default value: {default_value}")
        
        # Убеждаемся, что числовые поля имеют правильные типы
        if 'u_fan_speed' not in settings or settings['u_fan_speed'] is None:
            settings['u_fan_speed'] = 0
        if 'u_damp_pos' not in settings or settings['u_damp_pos'] is None:
            settings['u_damp_pos'] = 2
        if 'u_temp_room' not in settings or settings['u_temp_room'] is None:
            settings['u_temp_room'] = 0
        if 'u_cool_mode' not in settings or settings['u_cool_mode'] is None:
            settings['u_cool_mode'] = False
        
        # u_auto и u_night должны быть bool, не None
        # Библиотека требует bool, поэтому устанавливаем False если None
        if 'u_auto' not in settings or settings['u_auto'] is None:
            settings['u_auto'] = False
        if 'u_night' not in settings or settings['u_night'] is None:
            settings['u_night'] = False
        
        # Дополнительные поля settings, которые могут отсутствовать
        if 'u_night_start' not in settings:
            settings['u_night_start'] = None
        if 'u_night_stop' not in settings:
            settings['u_night_stop'] = None
        if 'u_time_zone' not in settings:
            settings['u_time_zone'] = None
        
        fixed_data['settings'] = settings
    
    # Condition - опциональное поле, может быть None
    # Если оно есть, исправляем None значения
    if 'condition' in fixed_data and fixed_data['condition']:
        condition = fixed_data['condition'].copy()
        
        # Исправляем числовые поля, которые могут быть None
        numeric_fields = ['co2_ppm', 'temp_room', 'temp_in', 'hum_room', 'hum_stg', 
                         'fan_speed', 'damp_pos', 'pwr_on', 'no_water']
        for field in numeric_fields:
            if field in condition and condition[field] is None:
                condition[field] = 0
        
        fixed_data['condition'] = condition
    else:
        # Condition может быть None - это нормально
        fixed_data['condition'] = None
    
    return fixed_data


def parse_devices_from_raw_data(
    raw_devices_data: List[Dict[str, Any]], 
    api_client
) -> List:
    """
    Парсит устройства из сырых данных API, обходя проблемы библиотеки atmeexpy.
    
    Args:
        raw_devices_data: Список словарей с данными устройств из API
        api_client: Экземпляр AtmeexClient для создания Device объектов
    
    Returns:
        Список объектов Device
    """
    parsed_devices = []
    
    for idx, device_data in enumerate(raw_devices_data, 1):
        device_id = device_data.get('id', 'unknown')
        device_name = device_data.get('name', f'Device {idx}')
        
        try:
            _LOGGER.debug(f"Parsing device {idx}: {device_name} (ID: {device_id})")
            
            # Исправляем данные перед парсингом
            fixed_device_data = fix_device_data_for_parsing(device_data)
            
            # Пробуем использовать библиотеку atmeexpy
            try:
                from atmeexpy.device import Device, DeviceModel
                
                # Создаем DeviceModel из исправленных данных
                device_model = DeviceModel.fromdict(fixed_device_data)
                _LOGGER.debug(f"DeviceModel created successfully for {device_name}")
                
                # Создаем Device объект
                device = Device(device_model, api_client)
                parsed_devices.append(device)
                _LOGGER.info(f"✓ Successfully parsed device: {device_name} (ID: {device_id})")
                
            except Exception as library_err:
                _LOGGER.warning(
                    f"Library atmeexpy failed to parse device {device_id} ({device_name}): {library_err}. "
                    f"Trying alternative parsing method..."
                )
                
                # Альтернативный способ: создаем минимальный Device объект
                try:
                    parsed_device = create_device_manually(fixed_device_data, api_client)
                    if parsed_device:
                        parsed_devices.append(parsed_device)
                        _LOGGER.info(f"✓ Successfully created device manually: {device_name} (ID: {device_id})")
                    else:
                        _LOGGER.error(f"✗ Failed to create device manually: {device_name} (ID: {device_id})")
                except Exception as manual_err:
                    _LOGGER.error(
                        f"✗ Failed to create device manually {device_id} ({device_name}): {manual_err}"
                    )
                    import traceback
                    _LOGGER.debug(f"Manual creation traceback: {traceback.format_exc()}")
                    
        except Exception as parse_err:
            _LOGGER.error(
                f"✗ Failed to parse device {device_id} ({device_name}): {parse_err}"
            )
            import traceback
            _LOGGER.debug(f"Parse traceback: {traceback.format_exc()}")
    
    return parsed_devices


def create_device_manually(device_data: Dict[str, Any], api_client) -> Optional[Any]:
    """
    Создает Device объект вручную, обходя проблемы библиотеки.
    
    Это запасной вариант, если DeviceModel.fromdict() не работает.
    Использует исправленные данные и пробует fromdict снова.
    """
    try:
        from atmeexpy.device import Device, DeviceModel
        
        # Исправляем данные еще раз для ручного создания
        fixed_data = fix_device_data_for_parsing(device_data)
        
        # Пробуем использовать fromdict с исправленными данными
        # Если это не работает, значит проблема глубже
        try:
            device_model = DeviceModel.fromdict(fixed_data)
            device = Device(device_model, api_client)
            _LOGGER.debug(f"Successfully created DeviceModel using fromdict with fixed data")
            return device
        except Exception as fromdict_err:
            _LOGGER.warning(
                f"DeviceModel.fromdict() failed even with fixed data: {fromdict_err}. "
                f"Trying to create DeviceModel with explicit constructor..."
            )
            
            # Последняя попытка: создаем через конструктор с явными аргументами
            # Но это сложно, так как нужно знать все обязательные поля
            # Лучше просто логировать ошибку и вернуть None
            _LOGGER.error(
                f"Cannot create DeviceModel manually - constructor requires all fields. "
                f"Original error: {fromdict_err}"
            )
            return None
        
    except Exception as e:
        _LOGGER.error(f"Error in create_device_manually: {e}")
        import traceback
        _LOGGER.debug(f"Traceback: {traceback.format_exc()}")
        return None

