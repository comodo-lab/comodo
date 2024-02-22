from json import dumps
from typing import Dict, Any, List


class cstate:
    """
    Represents the state of the controller, including the status, values being adjusted, and experiment configuration.
    """

    allowed_status = [
        "idle",
        "validating",
        "starting",
        "awaiting_sensors",
        "ready",
        "running",
        "stopping",
        "error",
    ]

    def __init__(self) -> None:
        """
        Initializes a new instance of the cstate class.
        """
        self.experiment_uid: str = None
        self.exp_file: str = None
        self.status: str = "idle"
        self.exp_config: Dict[str, Any] = None
        self.setpoints: List[Dict[str, Any]] = []
        self.sensors: Dict[str, Any] = {"configured": False}
        self.adjusting: AdjustingDict = AdjustingDict()
        self.schema_path: str = "schema_experiment.json"
        self.schema_sensor_heartbeat_path: str = "schema_sensor_heartbeat.json"

    def heartbeat(self) -> Dict[str, Any]:
        """
        Generates a dictionary with the attributes that will get added to the heartbeat mqtt messages.
        """
        heartbeat = {
            "experiment": self.experiment_uid,
            "status": self.status,
            "adjusting": self.adjusting,
        }
        return heartbeat

    def __str__(self) -> str:
        """
        Returns the string representation (heartbeat) of the cstate object.
        """
        return dumps(self.heartbeat())

    @property
    def experiment_uid(self) -> str:
        return self._experiment_uid

    @experiment_uid.setter
    def experiment_uid(self, value: str) -> None:
        """
        Sets the experiment UID.

        Args:
            value: The new experiment UID value. Must be a string or None.

        Raises:
            TypeError: If the provided experiment UID is not a string or None.
        """
        if not isinstance(value, (str, type(None))):
            raise TypeError(
                f"Experiment UID must be a string or None, cannot accept {type(value)}"
            )
        self._experiment_uid = value

    @property
    def exp_file(self) -> str:
        return self._exp_file

    @exp_file.setter
    def exp_file(self, value: str) -> None:
        """
        Sets the experiment file path.

        Args:
            value: The new experiment file path value. Must be a string or None.

        Raises:
            TypeError: If the provided experiment file path is not a string or None.
        """
        if not isinstance(value, (str, type(None))):
            raise TypeError(
                f"Experiment file path must be a string or None, cannot accept {type(value)}."
            )
        self._exp_file = value

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """
        Sets the status of the controller.

        Args:
            value: The new status value. Must be one of the allowed status values.

        Raises:
            ValueError: If the provided status is not one of the allowed status values.
        """
        if value not in self.allowed_status:
            raise ValueError(
                f"Invalid status: {value}. Status must be one of {self.allowed_status}."
            )
        self._status = value

    @property
    def exp_config(self) -> Dict[str, Any]:
        return self._exp_config

    @exp_config.setter
    def exp_config(self, value: Dict[str, Any]) -> None:
        """
        Sets the experiment configuration.

        Args:
            value: The new experiment configuration dict.

        Raises:
            TypeError: If the provided experiment configuration is not a dictionary or None.
        """
        if not isinstance(value, (dict, type(None))):
            raise TypeError(
                f"Experiment configuration must be a dictionary or None, cannot accept {type(value)}."
            )
        self._exp_config = value

    @property
    def setpoints(self) -> List[Dict[str, Any]]:
        return self._setpoints

    @setpoints.setter
    def setpoints(self, value: List[Dict[str, Any]]) -> None:
        """
        Sets the setpoints list.

        Args:
            value: The new setpoints list.

        Raises:
            TypeError: If the provided setpoints list is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(
                f"Setpoints must be a list of dictionaries, cannot accept {type(value)}."
            )
        self._setpoints = value

    @property
    def sensors(self) -> Dict[str, Any]:
        return self._sensors

    @sensors.setter
    def sensors(self, value: Dict[str, Any]) -> None:
        """
        Sets the sensors dictionary.

        Args:
            value: The new value for the entire sensors dictionary.

        Raises:
            TypeError: If the provided sensors dictionary is not a dictionary.
        """
        if not isinstance(value, dict):
            raise TypeError(
                f"Sensors must be a dictionary, cannot accept {type(value)}."
            )
        self._sensors = value

    @property
    def adjusting(self):
        return self._adjusting

    @adjusting.setter
    def adjusting(self, value: Dict[str, int]) -> None:
        """
        Sets the adjusting dictionary.
        It converts a plain dict to an AdjustingDict, to protect from unwanted elements or values.

        Args:
            value: The new value for the entire adjusting dictionary.

        Raises:
            ValueError: If the provided adjusting dictionary is incomplete or contains invalid keys.
        """
        self._adjusting = AdjustingDict(value)


class AdjustingDict(dict):
    """
    Represents a dictionary of adjusting values.
    The purpose of this class is to protect the adjusting dictionary from unwanted elements or values.
    """

    required_adjusting = [
        "T",
        "P",
        "D1",
        "D2",
    ]

    def __init__(self, *args, **kwargs) -> None:
        """
        Initializes a new instance of the AdjustingDict class.

        Raises:
            ValueError: If the provided adjusting dictionary is incomplete or contains invalid keys.
        """
        super().__init__({key: 0 for key in self.required_adjusting})
        if args or kwargs:
            tmp = dict(*args, **kwargs)
            if not all(key in tmp for key in self.required_adjusting):
                raise ValueError(
                    f"Incomplete adjusting keys. Adjusting must contain all of {self.required_adjusting}."
                )
            for key, value in tmp.items():
                self.__setitem__(key, value)

    def __setitem__(self, key: str, value: int) -> None:
        """
        Sets the value for the specified adjusting key.

        Args:
            key: The adjusting key.
            value: The adjusting value.

        Raises:
            ValueError: If the provided adjusting key is invalid or the value is not 0 or 1.
        """
        if key not in self.required_adjusting:
            raise ValueError(
                f"Invalid adjusting key: {key}. Adjusting must be one of {self.required_adjusting}."
            )
        elif value not in [0, 1]:
            raise ValueError(f"Invalid value for {key}: {value}. It must be 0 or 1.")
        super().__setitem__(key, value)

    def __delitem__(self, *args, **kwargs) -> None:
        """
        Raises a runtime error when attempting to delete items from the adjusting dictionary.
        """
        raise RuntimeError("Cannot delete items from the adjusting dict.")
