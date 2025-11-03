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

    async_add_entities([AtmeexDamperSelectEntity(device, coordinator) for device in coordinator.devices])

class AtmeexDamperSelectEntity(CoordinatorEntity, SelectEntity):
    """Select entity for damper position control."""
    
    _attr_options = ["open", "mixed", "closed"]
    _attr_icon = 'mdi:air-filter'
    
    def __init__(self, device: Device, coordinator: AtmeexDataCoordinator):
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        
        self.coordinator = coordinator
        self.device = device
        
        device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Atmeex {device.model.id}"
        
        self._attr_unique_id = f"{DOMAIN}_{device.model.id}_damper"
        self._attr_name = f"{device_name} Damper"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.model.id))},
            name=device_name,
            manufacturer="Atmeex",
            model="AirNanny Breezer",
        )
        
        self._update_state()
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        _LOGGER.debug(f"Setting damper position to {option} for {self.name}")
        
        # Маппинг: open=0, mixed=1, closed=2
        position_map = {
            "open": 0,
            "mixed": 1,
            "closed": 2
        }
        
        damp_pos = position_map.get(option)
        if damp_pos is None:
            _LOGGER.error(f"Invalid damper position option: {option}")
            return
        
        await self.device._set_params(DeviceSettingsSetModel(u_damp_pos=damp_pos))
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
        # Маппинг: 0=open, 1=mixed, 2=closed
        position_map = {
            0: "open",
            1: "mixed",
            2: "closed"
        }
        
        damp_pos = self.device.model.settings.u_damp_pos
        self._attr_current_option = position_map.get(damp_pos, "closed")
        self._attr_available = True

