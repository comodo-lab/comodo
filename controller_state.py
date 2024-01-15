from json import dumps


class cstate:
    def __init__(self):
        self.experiment = None
        self.status = "idle"
        self.adjusting = {
            "T": 0,
            "P": 0,
            "D1": 0,
            "D2": 0,
        }
        self.schema_path = "experiment_schema.json"
        self.exp_config = None

    def heartbeat(self):
        heartbeat = {
            "experiment": self.experiment,
            "status": self.status,
            "adjusting": self.adjusting,
        }
        return heartbeat

    def __str__(self):
        return dumps(self.heartbeat())
