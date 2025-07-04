import logging
from abc import ABC, abstractmethod
from typing import Optional

from localization import load_translation
from util.logger import MultiprocessingLogger


class GRBL(ABC):
    def __init__(self, device_name: str):
        self._logger: Optional[logging.Logger] = None
        self.device_name = device_name
        self.t = load_translation()

    @property
    def logger(self) -> logging.Logger:
        if not self._logger:
            self._logger = MultiprocessingLogger.get_logger(type(self).__name__)
        return self._logger

    @abstractmethod
    def write_gcode(self, command: str, retries: int = 3) -> None:
        """
        Writes the gcode command to grbl

        :param command:
            The raw gcode command string.
        :param retries:
            Number of times to retry the command should it fail.
            default is 3
        :return:
            None
        """
        pass
