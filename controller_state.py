class cstate:
    def __init__(self):
        self.experiment = None
        self.running = "idle"
        self.adjusting = None

    def __str__(self):
        cstate_print = ", ".join(
            [
                f"{attr}: {getattr(self, attr)}"
                for attr in ["experiment", "running", "adjusting"]
            ]
        )
        return cstate_print
