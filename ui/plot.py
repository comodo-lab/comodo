import json
import matplotlib.pyplot as plt
import numpy as np

def plot_data(data, title="Data Plot", xlabel="X-axis", ylabel="Y-axis"):
    """
    Plots the given data with specified title and axis labels.

    Args:
        data (dict): A dictionary where keys are x-values and values are y-values.
        title (str): Title of the plot.
        xlabel (str): Label for the x-axis.
        ylabel (str): Label for the y-axis.
    """
    """
    Plots time series of temp_left, temp_main, and temp_right from JSON-like input.

    Parameters:
        data (list of dict): Each dict must contain 'duration', 'temp_left', 'temp_main', 'temp_right'.
    """
    if not data:
        raise ValueError("Input data is empty.")

    special_keys = ['duration']

    # Extract cumulative time
    durations = [entry['duration'] for entry in data]
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


        axes[index].plot(time, values[index], label=key, color='tab:blue')
        axes[index].set_ylabel(key)
        axes[index].grid(True)

    axes[index].set_xlabel("Time")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    with open('data.json', 'r') as f:
        json_data = json.load(f)  # Load your JSON data here
    plot_data(json_data)
