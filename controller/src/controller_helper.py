import json
import numpy as np
import influxdb_client
import os
import csv
from datetime import datetime

from mqtt_clients import *
from error_helper import *


config = json.load(open("config/config.json"))


class internal_stop_msg:
    """
    Internal message to be passed to c_stopping, and stop the controller.
    It emulates the message components of a stop message from the UI.
    """

    def __init__(self, uid):
        self.topic = "controller/stop"
        p = {"uid": uid}
        self.payload = json.dumps(p).encode("utf-8")


def logarithmic_interpolation(start, end, num_steps):
    """
    Interpolates from start to end in a logarithmic fashion over num_steps.

    Arguments:
        start (float): The starting value (must be > 0 and != end).
        end (float): The ending value (must be > 0 and != start).
        num_steps (int): Number of interpolation steps (must be >= 2).

    Returns:
        np.ndarray: Array of interpolated values (length == num_steps)
    """
    if num_steps < 2:
        raise ValueError("num_steps must be at least 2 for interpolation.")
    if start <= 0 or end <= 0:
        raise ValueError("Logarithmic interpolation requires positive start and end values.")
    if start == end:
        return np.full(num_steps, start)

    log_start = np.log10(start)
    log_end = np.log10(end)

    log_space = np.linspace(log_start, log_end, num_steps)
    return np.power(10, log_space)


def linear_interpolation(start, end, num_steps):
    """
    Interpolates from start to end in a linear fashion over num_steps.

    Arguments:
        start (float): The starting value.
        end (float): The ending value.
        num_steps (int): Number of interpolation steps (must be >= 2).

    Returns:
        np.ndarray: Array of interpolated values (length == num_steps)
    """
    if num_steps < 2:
        raise ValueError("num_steps must be at least 2 for interpolation.")
    return np.linspace(start, end, num_steps)


def exponential_interpolation(start, end, num_steps):
    """
    Interpolates from start to end in an exponential fashion over num_steps.

    Arguments:
        start (float): Starting value.
        end (float): Ending value.
        num_steps (int): Number of interpolation steps (must be >= 2).

    Returns:
        np.ndarray: Array of interpolated values (length == num_steps)
    """
    if num_steps < 2:
        raise ValueError("num_steps must be at least 2 for interpolation.")
    if start == end:
        return np.full(num_steps, start)

    # Normalize to exponential curve between 0 and 1
    x = np.linspace(0, 1, num_steps)
    y = np.exp(x)  # exponential curve
    y = (y - y[0]) / (y[-1] - y[0])  # normalize to [0, 1]

    return start + y * (end - start)


def step_interpolation(start, end, num_steps):
    """
    Interpolates from start to end in a stepwise fashion over num_steps.

    Arguments:
        start (float): The starting value.
        end (float): The ending value.
        num_steps (int): Number of interpolation steps (must be >= 2).

    Returns:
        np.ndarray: Array of interpolated values (length == num_steps)
    """
    if num_steps < 2:
        raise ValueError("num_steps must be at least 2 for interpolation.")
    if start == end:
        return np.full(num_steps, start)

    interp = np.array([start for i in range(num_steps)])
    interp[-1] = end
    return interp


def split_setpoints(setpoint_list, resolution):
    """
    Interpolates the given setpoints to a given time resolution.
    It also converts from linear time to time intervals.
    """
    required_keys = ["time"]
    profiles = ["linear", "exponential", "logarithmic", "step"]

    variable_names = []
    sp_variables = {}

    for key in setpoint_list[0].keys():
        if key not in required_keys and "_proflie" not in key:
            variable_names.append(key)

    # Get given setpoints
    for key in required_keys:
        sp_times = np.array([sp["time"] for sp in setpoint_list])
        times = np.arange(min(sp_times), max(sp_times) + resolution, resolution)

    for name in variable_names:
        try:
            sp_variables[name] = np.array([(sp[name], sp[f"{name}_profile"]) for sp in setpoint_list])
        except KeyError:
            # Deafult to linear profile if not specified
            sp_variables[name] = np.array([(sp[name], "linear") for sp in setpoint_list])

    print(f"Interpolating setpoints for variables: {variable_names}, with resolution: {resolution}")
    print(f"Setpoints: {sp_variables}, for times: {times}")

    time_intervals = [times[i] - times[i - 1] for i in range(1, len(times))]
    time_intervals.insert(0, 0)

    # Interpolate each variable
    setpoint_values = [{'duration': duration} for duration in time_intervals]
    for name, values in sp_variables.items():
        previous_time = 0
        previous_setpoint = 0
        print(sp_times)
        step = 0
        interpolated_values = []
        for time in sp_times:
            print(f'Interpoltaed values {interpolated_values}')
            setpoint = values[step][0]
            profile = values[step][1]

            if step != 0:
                # Calculate the time interval since the last setpoint
                time_interval = time - previous_time
                if time_interval <= 0:
                    raise ValueError(f"Invalid time interval: {time_interval} for variable {name}")

                # Calculate the number of steps needed for interpolation
                num_steps = int(time_interval / resolution)
                if num_steps < 2:
                    if num_steps == 1:
                        print(f"Skipping interpolation for {name} due to insufficient steps: {num_steps}, just assigning setpoint value.")
                        new_values = [float(setpoint)]
                    else:
                        raise ValueError(f"Invalid number of steps for interpolation: {num_steps} for variable {name}")

                # Interpolate based on the profile type
                if profile == "linear":
                    new_values = linear_interpolation(float(previous_setpoint), float(setpoint), num_steps)
                elif profile == "exponential":
                    new_values = exponential_interpolation(float(previous_setpoint), float(setpoint), num_steps)
                elif profile == "logarithmic":
                    new_values = logarithmic_interpolation(float(previous_setpoint), float(setpoint), num_steps)
                elif profile == "step":
                    new_values = step_interpolation(float(previous_setpoint), float(setpoint), num_steps)
                else:
                    raise ValueError(f"Unknown profile type: {profiles}")
            else:
                # For the first setpoint, just use the setpoint value
                new_values = [float(setpoint)]

            interpolated_values.append(new_values[1:]) # Skip the first value as it is the previous setpoint
            previous_setpoint = setpoint
            previous_time = time
            step += 1

        # Assign to the setpoint_values
        for value in interpolated_values.enumerate():
            setpoint_values[i][name] = value
        print(f'Setpoint values: {setpoint_values}')

    return setpoint_values


data_path = "data"


def assign_serial_id(obj):
    """
    Assigns a serial id to the experiment, using the format: DYY-XXX,
    where YY is the last two digits of the current year, and XXX is a three digit serial.
    It then moves and renames the experiment file from tmp to to the data folder,
    and updates the cstate object accordingly.
    """
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


def dump_database_for_experiment(obj):
    """
    Dumps the influx databases for the experiment elapsed time.
    """
    t0 = obj.experiment_start_time
    tf = datetime.now()
    # get everything from influx database
    buckets = config["influxdb"]["buckets"]
    secret = json.load(open("config/.secret_influxdb_token.json"))
    client = influxdb_client.InfluxDBClient(
        url=config["influxdb"]["url"],
        token=secret["influxdb_token"],
        org=config["influxdb"]["org"],
    )
    query_api = client.query_api()
    exp_dir_path = obj.exp_file.replace(".json", "")
    if not os.path.exists(exp_dir_path):
        os.makedirs(exp_dir_path)
    for bucket in buckets:
        query = f'from(bucket: "{bucket}") |> range(start: {t0.isoformat()}Z, stop: {tf.isoformat()}Z)'
        data = query_api.query_csv(org=config["influxdb"]["org"], query=query)
        values = data.to_values()
        with open(f"{exp_dir_path}/{bucket}.csv", "w", newline="") as myfile:
            wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
            wr.writerows(values)
