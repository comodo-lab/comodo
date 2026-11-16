import numpy as np
import plotly.graph_objects as go
from utils.interpolation import split_setpoints


def plot_data_plotly(data, xlabel="Time", ylabel="Temperature", resolution=1):
    """
    Plots time series of temp_left, temp_main, and temp_right using Plotly.

    Parameters:
        data (list of dict): Each dict must contain 'duration' and one or more temperature fields.
        title (str): Title of the plot.
        xlabel (str): Label for the x-axis.
        ylabel (str): Label for the y-axis.
        resolution (float): Seconds between setpoints, as sent during the experiment.

    Returns:
        go.Figure: A Plotly figure object containing the plot.
    """
    if not data:
        raise ValueError("Input data is empty.")

    data = split_setpoints(data, resolution=resolution)

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
        # A marker per setpoint sent; also keeps a single-row experiment visible
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
