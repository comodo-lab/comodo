import json
import time as t
import numpy as np
from controller_state import *


def split_setpoints(setpoint_list, resolution):
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


def on_controller_message(client, msg, obj):
    if msg.topic == "controller/stop":
        t.sleep(3)
        obj.status = "idle"
        obj.experiment_uid = None
        obj.adjusting = AdjustingDict()
    if msg.topic == "controller/start":
        obj.status = "starting"
        obj.sensors = {}
        # Send sensor config
        for sensor in obj.exp_config["config"]["sensors"]:
            client.publish(f"controller/setup/{sensor['name']}", json.dumps(sensor))
        # Compute intermediate setpoints
        obj.setpoints = split_setpoints(
            obj.exp_config["experiment"], obj.exp_config["config"]["resolution"]
        )
        # Wait for sensors to be ready
        # while len(obj.sensors) < len(obj.exp_config["config"]["sensors"]):
        #     t.sleep(0.1)
        # Update experiment id and start experiment
        # client.publish("controller/run", obj.id)
