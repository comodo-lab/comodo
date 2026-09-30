import json
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from utils.interpolation import split_setpoints


def plot_data_plotly(data, xlabel="Time", ylabel="Temperature"):
    """
    Plots time series of temp_left, temp_main, and temp_right using Plotly.

    Parameters:
        data (list of dict): Each dict must contain 'duration' and one or more temperature fields.
        title (str): Title of the plot.
        xlabel (str): Label for the x-axis.
        ylabel (str): Label for the y-axis.

    Returns:
        go.Figure: A Plotly figure object containing the plot.
    """
    if not data:
        raise ValueError("Input data is empty.")

    data = split_setpoints(data, resolution=1)

    special_keys = ["duration"]
    keys = list(data[0].keys())

    # Compute cumulative time
    durations = [entry["duration"] for entry in data]
    time = np.cumsum(durations)

    # Prepare figure
    fig = go.Figure()

    # Plot each variable except 'duration'
    for key in keys:
        if key in special_keys:
            continue
        y = [entry[key] for entry in data]
        # Markers too, so a single-row experiment is still visible
        fig.add_trace(go.Scatter(x=time, y=y, mode="lines+markers", name=key))

    # Layout
    fig.update_layout(
        xaxis_title=xlabel,
        yaxis_title=ylabel,
        template="plotly_white",
        hovermode="x unified",
        legend={"xanchor": "auto", "yanchor": "auto"},
        margin={"autoexpand": True, "l": 0, "r": 0, "t": 0, "b": 0},
    )

    # fig.show()
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
