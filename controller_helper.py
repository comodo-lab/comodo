import json
import numpy as np
from mqtt_clients import *
from error_helper import *
from datetime import datetime
import os


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


data_path = "data"


def assign_serial_id(obj):
    temp_path = obj.exp_file
    current_year = str(datetime.now().year)[-2:]
    all_json = [f for f in os.listdir(data_path) if f.endswith(".json")]
    current_year_files = [f for f in all_json if f.startswith(f"D{current_year}-")]
    if len(current_year_files) == 0:
        serial = 1
    else:
        serials = [int(f.split("-")[1].split(".")[0]) for f in current_year_files]
        serials.sort()
        serial = serials[-1] + 1
    serial = str(serial).zfill(3)
    new_path = f"{data_path}/D{current_year}-{serial}.json"
    os.rename(temp_path, new_path)
    obj.experiment_uid = f"D{current_year}-{serial}"
    obj.exp_file = new_path
