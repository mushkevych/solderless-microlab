"""
The hardware package acts as the interface for the software to interact with any hardware. Currently split into 3 different
distinct modules, the temperature controller, stirrer, and reagent dispenser, which contain the functions needed for 
controller the temperature of the reactor, stirring, and dispensing any reagents into the microlab respectively.
Alternative implementations just need to implement a new class withthe functions of the base class in the base.py file 
for the module, as well as adding a call to that for a unique string setting to the create function in the __init__.py
file.
"""

import logging
import time
from enum import Enum
from typing import Literal, Any

import config
from hardware import devicelist
from hardware.devicelist import load_hardware_configuration
from hardware.util.lab_device_type import LabDevice
from localization import load_translation
from util.logger import MultiprocessingLogger


class MicroLabHardwareState(Enum):
    STARTING = 'STARTING'
    INITIALIZED = 'INITIALIZED'
    FAILED_TO_START = 'FAILED_TO_START'


class MicroLabHardware:
    _microlabHardware = None
    _logger = None

    def __init__(self, device_definitions: list[dict]):
        """
        Constructor. Initializes the hardware.
        """

        self.start_time: float = time.monotonic()
        self.devices: dict[str, LabDevice] = {}
        self.state = MicroLabHardwareState.STARTING
        self.error = None
        self.load_hardware(device_definitions)

        if self._logger is None:
            self._logger = self._get_logger()

    @classmethod
    def _get_logger(cls) -> logging.Logger:
        return MultiprocessingLogger.get_logger(__name__)

    @classmethod
    def get_microlab_hardware_controller(cls) -> 'MicroLabHardware':
        t = load_translation()

        if cls._logger is None:
            cls._logger = cls._get_logger()

        if not cls._microlabHardware:
            cls._logger.info('')
            cls._logger.info(t['starting-hardware-controller'])
            cls._logger.info(t['loading-hardware-configuration'])

            hardware_config = load_hardware_configuration()
            device_definitions = hardware_config['devices']
            cls._microlabHardware = MicroLabHardware(device_definitions)

        return cls._microlabHardware

    def load_hardware(self, device_definitions: list[dict]) -> tuple[bool, str]:
        """
        Loads and initializes the hardware devices

        :return:
            (True, '') on success.
            (False, message) on failure.
        """
        try:
            self.devices = devicelist.setup_devices(device_definitions)
            self.temp_controller = self.devices['reactor-temperature-controller']
            self.stirrer = self.devices['reactor-stirrer']
            self.reagent_dispenser = self.devices['reactor-reagent-dispenser']
            self.state = MicroLabHardwareState.INITIALIZED
            return True, ''
        except Exception as e:
            self._logger.exception(str(e))
            self.state = MicroLabHardwareState.FAILED_TO_START
            self.error = e
            return False, str(e)

    def turn_off_everything(self) -> None:
        """
        Stops any running hardware

        :return:
        None
        """
        self.turn_heater_off()
        self.turn_heater_pump_off()
        self.turn_cooler_off()
        self.turn_stirrer_off()

    def uptime_seconds(self) -> float:
        """
        The number of seconds since this package was started multiplied by config.hardwareSpeedup.

        This can effectively simulate time speedups for testing recipes.

        :return:
        The number of seconds since this package was started multiplied by config.hardwareSpeedup.
        """
        elapsed: float = time.monotonic() - self.start_time
        if hasattr(config, 'hardwareSpeedup'):
            speed = config.hardwareSpeedup
            if speed is not None:
                return elapsed * speed

        return elapsed

    def sleep(self, seconds: float) -> None:
        """
        Sleep for a number of seconds or if config.harwareSpeedup is configured, for a number of
        seconds/config.hardwareSpeedup

        The point of this method is to allow for speeding up time without modifying the recipes. This
        is especially useful for testing.

        :param seconds:
        Number of seconds to sleep. In real life will actually sleep for seconds/config.hardwareSpeedup.

        :return:
        None
        """
        if hasattr(config, 'hardwareSpeedup'):
            speed = config.hardwareSpeedup
            if speed is not None:
                time.sleep(seconds / speed)
                return

        time.sleep(seconds)

    def get_max_temperature(self) -> float:
        """
        :return:
        The max allowed temperature of the microlab in Celsius as a number
        """
        return self.temp_controller.get_max_temperature()

    def get_min_temperature(self) -> float:
        """
        :return:
        The minimum allowed temperature of the microlab in Celsius as a number
        """
        return self.temp_controller.get_min_temperature()

    def turn_heater_on(self) -> None:
        """
        Start heating the jacket.

        :return:
            None
        """
        self.temp_controller.turn_cooler_off()
        self.temp_controller.turn_heater_on()

    def turn_heater_off(self) -> None:
        """
        Stop heating the jacket.

        :return:
            None
        """
        self.temp_controller.turn_heater_off()

    def turn_heater_pump_on(self) -> None:
        """
        Turns on the heater pump.

        :return:
            None
        """
        self.temp_controller.turn_heater_pump_on()

    def turn_heater_pump_off(self) -> None:
        """
        Turns off the heater pump.

        :return:
            None
        """
        self.temp_controller.turn_heater_pump_off()

    def turn_cooler_on(self) -> None:
        """
        Start cooling the jacket.

        :return:
            None
        """
        self.temp_controller.turn_heater_off()
        self.temp_controller.turn_cooler_on()

    def turn_cooler_off(self) -> None:
        """
        Stop cooling the jacket.

        :return:
            None
        """
        self.temp_controller.turn_cooler_off()

    def turn_stirrer_on(self) -> None:
        """
        Start stirrer.

        :return:
            None
        """
        self.stirrer.turn_stirrer_on()

    def turn_stirrer_off(self) -> None:
        """
        Start stirrer.

        :return:
            None
        """
        self.stirrer.turn_stirrer_off()

    def get_temp(self) -> float:
        """
        Return the temperature.

        :return:
            The temperature as read from the sensor in Celsius
        """
        return self.temp_controller.get_temp()

    def get_pid_config(self) -> dict[str, Any]:
        """
        Return the temperature.

        :return:
            The temperature as read from the sensor in Celsius
        """
        return self.temp_controller.get_pid_config()

    def pump_dispense(self, pump_id: Literal['X', 'Y', 'Z'], volume: int, duration: int = None) -> float:
        """
        Dispense a number of ml from a particular pump.

        :param pump_id:
            The pump id. One of 'X', 'Y' or 'Z'
        :param volume:
            The number ml to dispense
        :param duration:
            optional - How long the dispensation should last in seconds
        :return:
            a Float Number indicating duration of the dispensation
        """
        return self.reagent_dispenser.dispense(pump_id, volume, duration)

    def get_pump_limits(self, pump_id: Literal['X', 'Y', 'Z']) -> dict:
        """
        Get maximum and minimum speed of specified pump.

        :param pump_id:
            The pump id. One of 'X' or 'Y' or 'Z'
        :return:
            dict
                minSpeed
                    Minimum speed the pump can dispense in ml/s
                maxSpeed
                    Maximum speed the pump can dispense in ml/s
        """
        return self.reagent_dispenser.get_pump_limits(pump_id)
