import json
import numpy as np
from mqtt_clients import *
from error_helper import *


class internal_stop_msg:
    """
    Internal message to be passed to c_stopping, and stop the controller.
    It emulates the message components of a stop message from the UI.
    """

    def __init__(self, uid):
        self.topic = "controller/stop"
        p = {"uid": uid}
        self.payload = json.dumps(p).encode("utf-8")


def split_setpoints(setpoint_list, resolution):
    """
    Interpolates the given setpoints to a given time resolution.
    """
    # Get given setpoints
    times = np.array([sp["time"] for sp in setpoint_list])
    pressures = np.array([sp["pressure"] for sp in setpoint_list])
    temperatures = np.array([sp["temperature"] for sp in setpoint_list])
    displacements_1 = np.array([sp["displacement 1"] for sp in setpoint_list])
    displacements_2 = np.array([sp["displacement 2"] for sp in setpoint_list])

    # Interpolate setpoints
    new_times = np.arange(min(times), max(times) + resolution, resolution)
    new_pressures = np.interp(new_times, times, pressures)
    new_temperatures = np.interp(new_times, times, temperatures)
    new_displacements_1 = np.interp(new_times, times, displacements_1)
    new_displacements_2 = np.interp(new_times, times, displacements_2)

    # Return list of dictionaries with the interpolated values
    return [
        {
            "time": t,
            "pressure": p,
            "temperature": temp,
            "displacement 1": d1,
            "displacement 2": d2,
        }
        for t, p, temp, d1, d2 in zip(
            new_times,
            new_pressures,
            new_temperatures,
            new_displacements_1,
            new_displacements_2,
        )
    ]


def assign_serial_id(obj):
    ### placeholder
    pass
    ###
