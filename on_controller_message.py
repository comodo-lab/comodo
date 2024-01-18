import json
import time as t
from controller_state import *


def on_controller_message(client, msg, obj):
    # if controller/stop pause 5 sec
    if msg.topic == "controller/stop":
        t.sleep(3)
        obj.status = "idle"
        obj.experiment_uid = None
        obj.adjusting = AdjustingDict()
