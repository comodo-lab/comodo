import numpy as np


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
    offset = 0
    if num_steps < 2:
        print("num_steps must be at least 2 for interpolation.")
        return np.array([end])
    if start <= 0 or end <= 0:
        if start < end:
            print(f"Start value {start} is not positive and smaller than end {end}.")
            offset = -start + 1
        else:
            print(f"End value {end} is not positive and smaller than start {start}.")
            offset = -end + 1
    if start == end:
        return np.full(num_steps, start)

    start += offset
    end += offset

    log_start = np.log10(start)
    log_end = np.log10(end)

    log_space = np.linspace(log_start, log_end, num_steps)
    return np.power(10, log_space) - offset


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

    for sp in setpoint_list:
        sp.pop('id')

    for key in setpoint_list[0].keys():
        if key not in required_keys and "_profile" not in key:
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

    time_intervals = [times[i] - times[i - 1] for i in range(1, len(times))]
    time_intervals.insert(0, 0)

    # Interpolate each variable
    setpoint_values = [{'duration': float(duration)} for duration in time_intervals]
    for name, values in sp_variables.items():
        previous_time = 0
        previous_setpoint = 0
        step = 0
        interpolated_values = np.array([])
        for time in sp_times:
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
                        continue
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

            interpolated_values = np.append(interpolated_values, new_values)  # Skip the first value as it is the previous setpoint
            previous_setpoint = setpoint
            previous_time = time
            step += 1

        # Assign to the setpoint_values
        for i, value in np.ndenumerate(interpolated_values):
            setpoint_values[i[0]][name] = float(value)

    return setpoint_values
