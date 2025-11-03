from datetime import timedelta
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
    api = AtmeexClient(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
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
        for device in self.devices:
            device_id = device.model.id
            device_name = device.model.name if hasattr(device.model, 'name') and device.model.name else f"Device {device_id}"
            has_condition = device.model.condition is not None
            
            if has_condition:
                condition_info = {
                    'co2_ppm': getattr(device.model.condition, 'co2_ppm', None),
                    'temp_room': getattr(device.model.condition, 'temp_room', None),
                    'temp_in': getattr(device.model.condition, 'temp_in', None),
                    'hum_room': getattr(device.model.condition, 'hum_room', None),
                }
                _LOGGER.debug(f"Device {device_name} (ID: {device_id}) condition data: {condition_info}")
            else:
                _LOGGER.debug(f"Device {device_name} (ID: {device_id}): condition is None")

        if self.entry.data[CONF_ACCESS_TOKEN] != self.api.auth._access_token or \
            self.entry.data[CONF_REFRESH_TOKEN] != self.api.auth._refresh_token:

            # Исправлено: используем copy() чтобы избежать изменения неизменяемого словаря
            data = self.entry.data.copy()
            data[CONF_ACCESS_TOKEN] = self.api.auth._access_token
            data[CONF_REFRESH_TOKEN] = self.api.auth._refresh_token

            await self.hass.config_entries.async_update_entry(self.entry, data=data)
