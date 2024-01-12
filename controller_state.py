class cstate:
    def __init__(self):
        self.experiment = None
        self.running = False
        self.adjusting = None

    def __str__(self):
        cstate_print = (
            f"experiment: {self.experiment}, "
            f"running: {self.running}"
            f"adjusting: {self.adjusting}"
        )
        return cstate_print
