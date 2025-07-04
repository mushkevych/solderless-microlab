from typing import Any

from hardware.temperaturecontroller.base import TempController


class SimulatedTempController(TempController):
    def __init__(self, sim_temp_controller_config: dict):
        super().__init__(sim_temp_controller_config, devices=None)
        self.maxTemp = sim_temp_controller_config['maxTemp']
        self.minTemp = sim_temp_controller_config['minTemp']
        self.heating = False
        self.cooling = False
        self.temperature = sim_temp_controller_config['temp'] if 'temp' in sim_temp_controller_config else 24

    def turn_heater_on(self) -> None:
        """
        Sets the heater flag for the simulation.

        :return:
        None
        """
        self.logger.info(self.t['turning-on-heat'])
        self.heating = True

    def turn_heater_off(self) -> None:
        """
        Un-sets the heater flag for the simulation.

        :return:
        None
        """
        self.logger.info(self.t['turning-off-heat'])
        self.heating = False

    def turn_heater_pump_on(self) -> None:
        self.logger.info(self.t['heat-pump-on'])

    def turn_heater_pump_off(self) -> None:
        self.logger.info(self.t['heat-pump-off'])

    def turn_cooler_on(self) -> None:
        """
        Sets the cooler flag for the simulation.

        :return:
        None
        """
        self.logger.info(self.t['turning-on-cool'])
        self.cooling = True

    def turn_cooler_off(self) -> None:
        """
        Un-sets the cooler flag for the simulation.

        :return:
        None
        """
        self.logger.info(self.t['turning-off-cool'])
        self.cooling = False

    def get_temp(self) -> float:
        """
        Simulates and returns temperature.

        Temperature starts off at 24C and changes every time the function is called as follows:
            heater flag on: +1C
            cooler flag on: -1C
            cooler and heater flag off: -0.1C
        :return:
        """
        # first-time initialization
        if self.temperature == -1:
            self.temperature = 24.0
        else:
            # determine change
            if self.heating:
                delta = 1.0
            elif self.cooling:
                delta = -1.0
            else:
                # move gently back toward 24C
                if self.temperature > 24.0:
                    delta = -0.1
                elif self.temperature < 24.0:
                    delta = 0.1
                else:
                    delta = 0.0

            # apply it
            self.temperature += delta

        self.logger.info(self.t['temperature-read-as'].format(self.temperature))
        return self.temperature

    def get_max_temperature(self) -> float:
        return self.maxTemp

    def get_min_temperature(self) -> float:
        return self.minTemp

    def get_pid_config(self) -> dict[str, Any]:
        """
        Read the temperature controller PID configuration

        :return:
        None if not specified, otherwise:
        object
            P: number
            I: number
            D: number
            proportionalOnMeasurement: Boolean (optional)
            differentialOnMeasurement: Boolean (optional)
        """
        return self.pid_config
