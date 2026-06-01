from json import dumps
from typing import Dict, Any, List
from datetime import datetime


class cstate:
    """
    Represents the state of the controller, including the status, values being adjusted, and experiment configuration.
    """

    allowed_status = [
        "idle",
        "validating",
        "starting",
        "awaiting_instruments",
        "ready",
        "running",
        "stopping",
        "error",
    ]

    __slots__ = [
        "_experiment_start_time",
        "_experiment_uid",
        "_exp_file",
        "_status",
        "_exp_config",
        "_setpoints",
        "_current_setpoint",
        "_past_setpoints",
        "_instruments",
        "_adjusting",
        "schema_path",
    ]

    def __init__(self) -> None:
        """
        Initializes a new instance of the cstate class.
        """
        self.experiment_start_time: datetime = None
        self.experiment_uid: str = None
        self.exp_file: str = None
        self.status: str = "idle"
        self.exp_config: Dict[str, Any] = None
        self.setpoints: List[Dict[str, Any]] = []
        self.current_setpoint: Dict[str, Any] = None
        self.past_setpoints: List[Dict[str, Any]] = []
        self.instruments: Dict[str, Any] = {"configured": False}
        self.adjusting: AdjustingDict = AdjustingDict()
        self.schema_path: str = "schemas/schema_experiment.json"

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

    def reset(self) -> None:
        """
        Resets the state of the controller to its initial values.
        """
        self.experiment_start_time = None
        self.experiment_uid = None
        self.exp_file = None
        self.status = "idle"
        self.exp_config = None
        self.setpoints = []
        self.current_setpoint = None
        self.past_setpoints = []
        self.instruments = {"configured": False}
        self.adjusting = AdjustingDict()

    @property
    def experiment_start_time(self) -> datetime:
        return self._experiment_start_time

    @experiment_start_time.setter
    def experiment_start_time(self, value: datetime) -> None:
        """
        Sets the experiment start time, used as a reference when dumping the database.

        Args:
            value: The new experiment start time value. Must be a datetime object or None.

        Raises:
            TypeError: If the provided experiment start time is not a datetime object or None.
        """
        if not isinstance(value, (datetime, type(None))):
            raise TypeError(
                f"Experiment start time must be a datetime or None, cannot accept {type(value)}"
            )
        self._experiment_start_time = value

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
    def current_setpoint(self) -> Dict[str, Any]:
        return self._current_setpoint

    @current_setpoint.setter
    def current_setpoint(self, value: Dict[str, Any]) -> None:
        """
        Sets the current setpoint.

        Args:
            value: The new value for the entire current setpoint.

        Raises:
            TypeError: If the provided current setpoint dictionary is not a dictionary or None.
        """
        if not isinstance(value, (dict, type(None))):
            raise TypeError(
                f"Current setpoint must be a dictionary or None, cannot accept {type(value)}."
            )
        self._current_setpoint = value

    @property
    def past_setpoints(self) -> List[Dict[str, Any]]:
        return self._past_setpoints

    @past_setpoints.setter
    def past_setpoints(self, value: List[Dict[str, Any]]) -> None:
        """
        Sets the past setpoints list.

        Args:
            value: The new past setpoints list.

        Raises:
            TypeError: If the provided past setpoints list is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(
                f"Past setpoints must be a list of dictionaries, cannot accept {type(value)}."
            )
        self._past_setpoints = value

    @property
    def instruments(self) -> Dict[str, Any]:
        return self._instruments

    @instruments.setter
    def instruments(self, value: Dict[str, Any]) -> None:
        """
        Sets the instruments dictionary.

        Args:
            value: The new value for the entire instruments dictionary.

        Raises:
            TypeError: If the provided instruments dictionary is not a dictionary.
        """
        if not isinstance(value, dict):
            raise TypeError(
                f"Instruments must be a dictionary, cannot accept {type(value)}."
            )
        self._instruments = value

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
