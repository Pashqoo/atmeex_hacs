import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE, CONCENTRATION_PARTS_PER_MILLION
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
        
        # Создаем sensors для всех устройств (condition может появиться позже)
        entities.append(AtmeexCO2Sensor(device, coordinator, device_name))
        entities.append(AtmeexTemperatureSensor(device, coordinator, device_name))
        entities.append(AtmeexHumiditySensor(device, coordinator, device_name))
        entities.append(AtmeexTemperatureInSensor(device, coordinator, device_name))
        entities.append(AtmeexHumidityTargetSensor(device, coordinator, device_name))
        entities.append(AtmeexFanSpeedSensor(device, coordinator, device_name))
        entities.append(AtmeexDamperPositionSensor(device, coordinator, device_name))
        entities.append(AtmeexFirmwareVersionSensor(device, coordinator, device_name))
    
    _LOGGER.debug(f"Creating {len(entities)} sensor entities for {len(coordinator.devices)} devices")
    async_add_entities(entities)

class AtmeexCO2Sensor(CoordinatorEntity, SensorEntity):
    """Sensor for CO2 concentration."""
    
    _attr_device_class = SensorDeviceClass.CO2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_icon = 'mdi:molecule-co2'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_co2"
        self._attr_name = f"{device_name} CO2"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        if self.device.model.condition:
            co2_value = getattr(self.device.model.condition, 'co2_ppm', None)
            if co2_value is not None:
                self._attr_native_value = co2_value
                self._attr_available = True
            else:
                _LOGGER.debug(f"CO2 sensor {self.name}: condition.co2_ppm is None or missing")
                self._attr_native_value = None
                self._attr_available = False
        else:
            _LOGGER.debug(f"CO2 sensor {self.name}: device.model.condition is None")
            self._attr_native_value = None
            self._attr_available = False

class AtmeexTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor for room temperature."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = 'mdi:thermometer'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_temperature"
        self._attr_name = f"{device_name} Temperature"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        if self.device.model.condition:
            temp_value = getattr(self.device.model.condition, 'temp_room', None)
            if temp_value is not None:
                # temp_room в API - это температура * 10
                self._attr_native_value = temp_value / 10.0
                self._attr_available = True
            else:
                _LOGGER.debug(f"Temperature sensor {self.name}: condition.temp_room is None or missing")
                self._attr_native_value = None
                self._attr_available = False
        else:
            _LOGGER.debug(f"Temperature sensor {self.name}: device.model.condition is None")
            self._attr_native_value = None
            self._attr_available = False

class AtmeexTemperatureInSensor(CoordinatorEntity, SensorEntity):
    """Sensor for inlet temperature."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = 'mdi:thermometer'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_temperature_in"
        self._attr_name = f"{device_name} Temperature In"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        if self.device.model.condition:
            temp_value = getattr(self.device.model.condition, 'temp_in', None)
            if temp_value is not None:
                # temp_in в API - это температура * 10
                self._attr_native_value = temp_value / 10.0
                self._attr_available = True
            else:
                _LOGGER.debug(f"Temperature In sensor {self.name}: condition.temp_in is None or missing")
                self._attr_native_value = None
                self._attr_available = False
        else:
            _LOGGER.debug(f"Temperature In sensor {self.name}: device.model.condition is None")
            self._attr_native_value = None
            self._attr_available = False

class AtmeexHumiditySensor(CoordinatorEntity, SensorEntity):
    """Sensor for room humidity."""
    
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = 'mdi:water-percent'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_humidity"
        self._attr_name = f"{device_name} Humidity"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        if self.device.model.condition:
            hum_value = getattr(self.device.model.condition, 'hum_room', None)
            if hum_value is not None:
                self._attr_native_value = hum_value
                self._attr_available = True
            else:
                _LOGGER.debug(f"Humidity sensor {self.name}: condition.hum_room is None or missing")
                self._attr_native_value = None
                self._attr_available = False
        else:
            _LOGGER.debug(f"Humidity sensor {self.name}: device.model.condition is None")
            self._attr_native_value = None
            self._attr_available = False

class AtmeexHumidityTargetSensor(CoordinatorEntity, SensorEntity):
    """Sensor for target humidity."""
    
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = 'mdi:target'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_humidity_target_sensor"
        self._attr_name = f"{device_name} Humidity Target"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        # Используем значение из settings (установка) или condition (текущая цель)
        if self.device.model.condition:
            self._attr_native_value = self.device.model.condition.hum_stg
        else:
            self._attr_native_value = self.device.model.settings.u_hum_stg
        self._attr_available = True

class AtmeexFanSpeedSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current fan speed."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = 'mdi:fan'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_fan_speed"
        self._attr_name = f"{device_name} Fan Speed"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        if self.device.model.condition:
            # Возвращаем скорость как 1-7 (для удобства)
            self._attr_native_value = self.device.model.condition.fan_speed + 1
            self._attr_available = True
        else:
            # Если нет condition, используем settings
            self._attr_native_value = self.device.model.settings.u_fan_speed + 1
            self._attr_available = True

class AtmeexDamperPositionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for damper position."""
    
    _attr_icon = 'mdi:air-filter'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_damper_position"
        self._attr_name = f"{device_name} Damper Position"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        # Маппинг: 0 = "Open", 1 = "Mixed", 2 = "Closed"
        position_map = {
            0: "Open",
            1: "Mixed",
            2: "Closed"
        }
        
        if self.device.model.condition:
            damp_pos = self.device.model.condition.damp_pos
        else:
            damp_pos = self.device.model.settings.u_damp_pos
        
        self._attr_native_value = position_map.get(damp_pos, "Unknown")
        self._attr_available = True

class AtmeexFirmwareVersionSensor(CoordinatorEntity, SensorEntity):
    """Sensor for firmware version."""
    
    _attr_icon = 'mdi:chip'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator, device_name: str):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_firmware_version"
        self._attr_name = f"{device_name} Firmware Version"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
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
        # Предпочитаем версию из condition, иначе из model
        if self.device.model.condition:
            self._attr_native_value = self.device.model.condition.firmware_version
        else:
            self._attr_native_value = self.device.model.fw_ver
        self._attr_available = True

