from json import dumps
from typing import Dict, Any


class cstate:
    """
    Represents the state of the controller, including the status, values being adjusted, and experiment configuration.
    """

    allowed_status = [
        "idle",
        "validating",
        "starting",
        "awaiting_sensors",
        "running",
        "stopping",
        "error",
    ]

    def __init__(self) -> None:
        """
        Initializes a new instance of the cstate class.
        """
        self.experiment_uid: str = None
        self.status: str = "idle"
        self.adjusting: AdjustingDict = AdjustingDict()
        self.schema_path: str = "schema_experiment.json"
        self.exp_config: Any = None

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
