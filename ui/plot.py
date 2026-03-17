import json
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import OrderedDict
from utils.interpolation import split_setpoints


def plot_data_plotly(data, xlabel="Time (s)"):
    if not data:
        raise ValueError("Input data is empty.")

    data = split_setpoints(data, resolution=1)

    special_keys = ["duration"]
    keys = [k for k in data[0].keys() if k not in special_keys]

    durations = [entry["duration"] for entry in data]
    time = np.cumsum(durations)

    # Group variables by type (part after "/"), preserving order
    groups = OrderedDict()
    for key in keys:
        if "/" in key:
            var_type = key.split("/", 1)[1]
        else:
            var_type = key
        groups.setdefault(var_type, []).append(key)

    n_groups = len(groups)
    fig = make_subplots(
        rows=n_groups,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=[vt.replace("_", " ").capitalize() for vt in groups],
    )

    for row, (var_type, var_keys) in enumerate(groups.items(), start=1):
        for key in var_keys:
            label = key.split("/")[0].replace("_", " ").capitalize()
            y = [entry[key] for entry in data]
            fig.add_trace(
                go.Scatter(x=time, y=y, mode="lines", name=label),
                row=row,
                col=1,
            )

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        margin={"autoexpand": True, "l": 0, "r": 0, "t": 30, "b": 0},
        height=300 * n_groups,
    )
    fig.update_xaxes(title_text=xlabel, row=n_groups, col=1)

    return fig


def plot_data_matplotlib(data, xlabel="X-axis", ylabel="Y-axis"):
    """
    Plots the given data with axis labels.

    Args:
        data (dict): A dictionary where keys are x-values and values are y-values.
        xlabel (str): Label for the x-axis.
        ylabel (str): Label for the y-axis.
    """
    if not data:
        raise ValueError("Input data is empty.")

    special_keys = ["duration"]

    # Extract cumulative time
    durations = [entry["duration"] for entry in data]
    time = np.cumsum(durations)

    # Plotting
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    # Extract parameter values
    values = [[] for _ in range(len(data[0].keys()) - len(special_keys))]
    keys = list(data[0].keys())
    for key in keys:
        if key in special_keys:
            print(f"Skipping special key: {key}")
            continue
        index = keys.index(key) - len(special_keys)
        values[index] = [entry[key] for entry in data]

        axes[index].plot(time, values[index], label=key, color="tab:blue")
        axes[index].set_ylabel(key)
        axes[index].grid(True)

    axes[index].set_xlabel("Time")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    with open("data.json", "r") as f:
        json_data = json.load(f)  # Load your JSON data here
    plot_data_matplotlib(json_data)
