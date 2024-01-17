from json import dumps


class cstate:
    allowed_status = [
        "idle",
        "validating",
        "starting",
        "running",
        "stopping",
        "error",
    ]

    def __init__(self):
        self.experiment_uid = None
        self.status = "idle"
        self.adjusting = AdjustingDict()
        self.schema_path = "experiment_schema.json"
        self.exp_config = None

    def heartbeat(self):
        heartbeat = {
            "experiment": self.experiment_uid,
            "status": self.status,
            "adjusting": self.adjusting,
        }
        return heartbeat

    def __str__(self):
        return dumps(self.heartbeat())

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        if value not in self.allowed_status:
            raise ValueError(
                f"Invalid status: {value}. Status must be one of {self.allowed_status}."
            )
        self._status = value

    @property
    def adjusting(self):
        return self._adjusting

    @adjusting.setter
    def adjusting(self, value):
        self._adjusting = AdjustingDict(value)


class AdjustingDict(dict):
    required_adjusting = [
        "T",
        "P",
        "D1",
        "D2",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__({key: 0 for key in self.required_adjusting})
        if args or kwargs:
            tmp = dict(*args, **kwargs)
            if not all(key in tmp for key in self.required_adjusting):
                raise ValueError(
                    f"Incomplete adjusting keys. Adjusting must contain all of {self.required_adjusting}."
                )
            for key, value in tmp.items():
                self.__setitem__(key, value)

    def __setitem__(self, key, value):
        if key not in self.required_adjusting:
            raise ValueError(
                f"Invalid adjusting key: {key}. Adjusting must be one of {self.required_adjusting}."
            )
        elif value not in [0, 1]:
            raise ValueError(f"Invalid value for {key}: {value}. It must be 0 or 1.")
        super().__setitem__(key, value)

    def __delitem__(self, *args, **kwargs):
        raise RuntimeError("Cannot delete items from the adjusting dict.")
