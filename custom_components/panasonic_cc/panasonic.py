
from datetime import timedelta
import logging
from datetime import datetime

from typing import Any, Dict, Optional, List
from homeassistant.util import Throttle
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.climate.const import ATTR_HVAC_MODE

from .const import PRESET_LIST, OPERATION_LIST

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

def api_call_login(func):
    def wrapper_call(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            args[0]._api.login()
            func(*args, **kwargs)
    return wrapper_call

class PanasonicApiDevice:

    def __init__(self, hass: HomeAssistantType, api, device, force_outside_sensor, enable_energy_sensor):
        from pcomfortcloud import constants
        self.hass = hass
        self._api = api
        self.device = device
        self.force_outside_sensor = force_outside_sensor
        self.enable_energy_sensor = enable_energy_sensor
        self.id = device['id']
        self.name = device['name']
        self.group = device['group']
        self.data = None
        self.energy_data = None
        self.last_energy_reading = 0
        self.last_energy_reading_time = None
        self.current_power_value = 0
        self.current_power_counter = 0
        self._available = True
        self.constants = constants
        

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, **kwargs):
        await self.do_update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update_energy(self, **kwargs):
        await self.do_update_energy()

    async def do_update(self):
        try:
            data= await self.hass.async_add_executor_job(self._api.get_device,self.id)
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device))
            await self.hass.async_add_executor_job(self._api.login)
            data= await self.hass.async_add_executor_job(self._api.get_device,self.id)

        if data is None:
            self._available = False
            _LOGGER.debug("Received no data for device {id}".format(**self.device))
            return
        self._available = True
        self.data = data

    async def do_update_energy(self):
        try:
            data= await self.hass.async_add_executor_job(self._api.history,self.id,"Day",datetime.now().strftime("%Y%m%d"))
            
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device))
            await self.hass.async_add_executor_job(self._api.login)
            data= await self.hass.async_add_executor_job(self._api.get_device,self.id)

        if data is None:
            _LOGGER.debug("Received no energy data for device {id}".format(**self.device))
            return
        t1 = datetime.now()
        c_energy = data['parameters']['energyConsumption']
        if self.last_energy_reading_time is not None:
            if c_energy != self.last_energy_reading:                
                d = (t1 - self.last_energy_reading_time).total_seconds() / 60 / 60
                p = round((c_energy - self.last_energy_reading)*1000 / d)
                self.last_energy_reading = c_energy
                self.last_energy_reading_time = t1
                if p >= 0:
                    self.current_power_value = p
                self.current_power_counter = 0
            else:
                self.current_power_counter += 1
                if self.current_power_counter > 30:
                    self.current_power_value = 0
        else:
            self.last_energy_reading = c_energy
            self.last_energy_reading_time = t1
        self.energy_data = data

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": { ("panasonic_cc", self.id) },
            "manufacturer": "Panasonic",
            "model": self.device['model'],
            "name": self.name,
        }

    @property
    def is_on(self):
        return bool( self.data['parameters']['power'].value )

    @property
    def inside_temperature(self):
        if self.data['parameters']['temperatureInside'] != 126:
            return self.data['parameters']['temperatureInside']
        return None

    @property
    def support_inside_temperature(self):
        return self.inside_temperature != None

    @property
    def outside_temperature(self):
        temp = self.data['parameters']['temperatureOutside']
        if temp != 126:
            return temp
        return None

    @property
    def support_outside_temperature(self):
        if self.force_outside_sensor:
            return True
        return self.outside_temperature != 126

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self.data['parameters']['temperature'] != 126:
            return self.data['parameters']['temperature']
        return None

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.data['parameters']['fanSpeed'].name

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self.data['parameters']['airSwingVertical'].name

    @property
    def hvac_mode(self):
        """Return the current operation."""
        return self.data['parameters']['mode'].name

    @property
    def eco_mode(self) -> Optional[str]:
        return self.data['parameters']['eco'].name

    @property
    def nanoe_mode(self):
        p = self.data['parameters']
        if 'nanoe' in p:
            return p['nanoe']
        return None

    @property
    def energy_sensor_enabled(self):
        return self.enable_energy_sensor

    @property
    def daily_energy(self):
        if not self.enable_energy_sensor:
            return None
        if self.energy_data is not None:
            return self.energy_data['parameters']['energyConsumption']
        return None

    @property
    def current_power(self):
        if not self.enable_energy_sensor:
            return None
        return self.current_power_value

    async def turn_off(self):
        await self.hass.async_add_executor_job(
            self.set_device,
            { "power": self.constants.Power.Off }
        )
        await self.do_update()

    async def turn_on(self):
        await self.hass.async_add_executor_job(
            self.set_device,
            { "power": self.constants.Power.On }
        )
        await self.do_update()
        
    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Set %s ecomode %s", self.name, preset_mode)
        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "eco": self.constants.EcoMode[ PRESET_LIST[preset_mode] ]
            })
        await self.do_update()

    async def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        new_values = { "temperature": target_temp }

        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            new_values['power'] = self.constants.Power.On
            new_values['mode'] = self.constants.OperationMode[OPERATION_LIST[hvac_mode]]

        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)

        await self.hass.async_add_executor_job(
            self.set_device,
            new_values
        )
        await self.do_update()
        

    async def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { "fanSpeed": self.constants.FanSpeed[fan_mode] }
        )
        await self.do_update()
    
    async def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s mode %s", self.name, hvac_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "mode": self.constants.OperationMode[OPERATION_LIST[hvac_mode]] 
            })

        await self.do_update()

    async def set_swing_mode(self, swing_mode):
        """Set swing mode."""
        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)
        if swing_mode == 'Auto':
            automode = self.constants.AirSwingAutoMode["AirSwingUD"]
        else:
            automode = self.constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "airSwingVertical": self.constants.AirSwingUD[swing_mode],
                "fanAutoMode": automode
            })
        await self.do_update()

    async def set_nanoe_mode(self, nanoe_mode):
        """Set new nanoe mode."""
        _LOGGER.debug("Set %s nanoe mode %s", self.name, nanoe_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { "nanoe": self.constants.NanoeMode[nanoe_mode] }
        )
        await self.do_update()

    @api_call_login
    def set_device(self, args):
        self._api.set_device(
            self.id,
            **args
        )
