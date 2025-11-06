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
    
    # Исправляем settings
    if 'settings' in fixed_data and fixed_data['settings']:
        settings = fixed_data['settings'].copy()
        
        # Исправляем u_hum_stg - должно быть int, но может быть None
        # Удаляем поле если None, чтобы библиотека использовала значение по умолчанию
        if 'u_hum_stg' in settings and settings['u_hum_stg'] is None:
            del settings['u_hum_stg']
        
        # Исправляем другие поля, которые могут быть None
        # Для Optional полей удаляем None, для обязательных устанавливаем значения по умолчанию
        if 'u_fan_speed' in settings and settings['u_fan_speed'] is None:
            settings['u_fan_speed'] = 0
        if 'u_damp_pos' in settings and settings['u_damp_pos'] is None:
            settings['u_damp_pos'] = 2  # Закрыта по умолчанию
        if 'u_temp_room' in settings and settings['u_temp_room'] is None:
            settings['u_temp_room'] = 0
        # u_auto и u_night могут быть None (Optional), удаляем их если None
        if 'u_auto' in settings and settings['u_auto'] is None:
            del settings['u_auto']
        if 'u_night' in settings and settings['u_night'] is None:
            del settings['u_night']
        
        # Исправляем u_cool_mode - должно быть bool
        if 'u_cool_mode' in settings and settings['u_cool_mode'] is None:
            settings['u_cool_mode'] = False
        
        fixed_data['settings'] = settings
    
    # Исправляем condition, если он есть
    if 'condition' in fixed_data and fixed_data['condition']:
        condition = fixed_data['condition'].copy()
        
        # Исправляем числовые поля, которые могут быть None
        numeric_fields = ['co2_ppm', 'temp_room', 'temp_in', 'hum_room', 'hum_stg', 
                         'fan_speed', 'damp_pos', 'pwr_on', 'no_water']
        for field in numeric_fields:
            if field in condition and condition[field] is None:
                if field in ['co2_ppm', 'temp_room', 'temp_in', 'hum_room', 'hum_stg', 
                            'fan_speed', 'damp_pos', 'pwr_on', 'no_water']:
                    condition[field] = 0
        
        fixed_data['condition'] = condition
    
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
    """
    try:
        from atmeexpy.device import Device, DeviceModel
        
        # Создаем DeviceModel вручную, устанавливая только доступные поля
        device_model = DeviceModel()
        
        # Устанавливаем основные поля
        if 'id' in device_data:
            device_model.id = device_data['id']
        if 'name' in device_data:
            device_model.name = device_data['name']
        if 'mac' in device_data:
            device_model.mac = device_data['mac']
        if 'online' in device_data:
            device_model.online = device_data['online']
        if 'model' in device_data:
            device_model.model = device_data['model']
        if 'fw_ver' in device_data:
            device_model.fw_ver = device_data['fw_ver']
        
        # Устанавливаем settings
        if 'settings' in device_data and device_data['settings']:
            from atmeexpy.device import DeviceSettingsModel
            settings = DeviceSettingsModel()
            
            settings_data = device_data['settings']
            if 'id' in settings_data:
                settings.id = settings_data['id']
            if 'device_id' in settings_data:
                settings.device_id = settings_data['device_id']
            if 'u_pwr_on' in settings_data:
                settings.u_pwr_on = settings_data['u_pwr_on'] if settings_data['u_pwr_on'] is not None else False
            if 'u_fan_speed' in settings_data:
                settings.u_fan_speed = settings_data['u_fan_speed'] if settings_data['u_fan_speed'] is not None else 0
            if 'u_damp_pos' in settings_data:
                settings.u_damp_pos = settings_data['u_damp_pos'] if settings_data['u_damp_pos'] is not None else 2
            if 'u_temp_room' in settings_data:
                settings.u_temp_room = settings_data['u_temp_room'] if settings_data['u_temp_room'] is not None else 0
            if 'u_hum_stg' in settings_data:
                settings.u_hum_stg = settings_data['u_hum_stg'] if settings_data['u_hum_stg'] is not None else None
            if 'u_auto' in settings_data:
                settings.u_auto = settings_data['u_auto'] if settings_data['u_auto'] is not None else None
            if 'u_night' in settings_data:
                settings.u_night = settings_data['u_night'] if settings_data['u_night'] is not None else None
            if 'u_cool_mode' in settings_data:
                settings.u_cool_mode = settings_data['u_cool_mode'] if settings_data['u_cool_mode'] is not None else False
            if 'u_night_start' in settings_data:
                settings.u_night_start = settings_data['u_night_start']
            if 'u_night_stop' in settings_data:
                settings.u_night_stop = settings_data['u_night_stop']
            if 'u_time_zone' in settings_data:
                settings.u_time_zone = settings_data['u_time_zone']
            
            device_model.settings = settings
        
        # Condition устанавливаем как None - он будет получен позже через API
        device_model.condition = None
        
        # Создаем Device объект
        device = Device(device_model, api_client)
        
        return device
        
    except Exception as e:
        _LOGGER.error(f"Error in create_device_manually: {e}")
        import traceback
        _LOGGER.debug(f"Traceback: {traceback.format_exc()}")
        return None

