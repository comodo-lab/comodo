# User Interface

The user interface (UI) is a web app, built with [Dash](https://dash.plotly.com/), to design, start, stop and monitor experiments.
It is part of the core stack, and is available at `localhost:8501` on the core host.

It talks to the rest of Comodo only through MQTT messages: it sends experiments to the [controller](../controller/README.md),
and shows the state of the stack from the heartbeats and errors published by each component.

- [User Interface](#user-interface)
  - [Pages](#pages)
    - [Header](#header)
    - [Experiment settings](#experiment-settings)
    - [Operation](#operation)
  - [Saved settings](#saved-settings)
  - [Starting and stopping an experiment](#starting-and-stopping-an-experiment)
  - [MQTT topics](#mqtt-topics)
  - [Configuration](#configuration)
  - [Code structure](#code-structure)
  - [Running tests](#running-tests)

## Pages

### Header
The header is shown on every page, with:
- The controller's status and the current experiment id.
- The status of every instrument and setpoint controller in `comodo.yaml`, from their latest heartbeat.
  Components that have stopped sending heartbeats are shown as such.
- When the latest heartbeat was received.

### Experiment settings
These pages define an experiment. They are pre-filled from `comodo.yaml`, and each can be [saved and loaded](#saved-settings).
- **Timeline**: The setpoints of the experiment, as an editable table, and a graph of the setpoints that will be sent.
  Each row has a `time` (in seconds from the start), a setpoint for each variable that drives an actuator, and how to reach it (`linear`, `exponential`, `logarithmic` or `step`).
- **Instruments**: The live configuration sent to each instrument, as rows of `name`, `key` and `value`.
  `name` is an instrument (`instrument`), or one of its variables (`instrument/variable`).
  Every variable in the timeline needs a numeric `tolerance`, which defaults to the one in `comodo.yaml`.
- **PID Controllers**: The PID parameters of each setpoint controller, which default to the ones in `comodo.yaml` (or the setpoint controller's defaults).
- **Global**: Settings for the whole experiment. Currently the `resolution`: the time in seconds between the setpoints sent to the instruments.

See [experiment message](../controller/README.md#experiment-message) in the controller's README for how these are sent to the controller, and what it checks.

### Operation
- **Experiment Control**: The button to start or stop an experiment (see [below](#starting-and-stopping-an-experiment)).
  It also has a manual control panel, with a slider and readout for each variable, which is currently disabled until instruments support manual control.
- **Data Monitor**: The Grafana dashboard, embedded. See `GRAFANA_DASHBOARD_URL` in the [main README](../README.md#environment-variables) to use a different dashboard.
- **Event Log**: The errors published by any component (on `error/#`), and the main experiment events, newest first.
  The tab shows the number of errors not yet seen. Only the latest 500 entries are kept.

## Saved settings
Each of the experiment settings pages has a bar to load a saved version, name it, and save it.
- Settings are saved as YAML files in the `ui/data/` folder (mounted in the container at `/ui_data`), with a folder for each kind:
  `experiments/`, `instruments/`, `configs/` and `spcs/`.
- Saving never overwrites a file: it always creates a new one, prefixed with a timestamp.
  A modified version that keeps its name gets the date and time appended to it.
- When the UI is opened, each page starts from the latest saved version, so an experiment can be started without visiting every page.
  If nothing has been saved yet, the defaults from `comodo.yaml` are saved first.
- Saved settings are fitted to the current `comodo.yaml` when loaded, as it may have changed since they were saved.
- When an experiment is started, any unsaved changes are saved, and a run is saved in `runs/`, linking the files used to start it.

## Starting and stopping an experiment
When the start button is pressed, the UI:
1. Checks the instrument and PID settings. If they are invalid, it publishes an error on `error/ui`, and does not start the experiment.
2. Saves any unsaved settings, and the run.
3. Publishes the experiment on `ui/start`, with a temporary id. The controller then validates it, assigns its experiment id, and runs it.

The button follows the controller's heartbeat: it shows start when the controller is idle, stop while an experiment is running,
and is disabled while the controller is busy validating or stopping.
Pressing stop publishes the experiment id on `ui/stop`.

## Resetting the instruments
The reset button, below the manual control toggle, publishes `ui/reset` (after asking for confirmation),
and the controller then resets every instrument and setpoint controller to its default setpoints.
This clears a safe stop (see the [firmware's safe stop](../firmware/README.md#safe-stop)), so make sure whatever caused it has been fixed first.
It is only enabled while the controller is idle, as a running experiment has to be stopped first.

## MQTT topics
The UI subscribes to:
- `controller/heartbeat`, `instruments/<name>/heartbeat` and `setpoint_controllers/<id>/heartbeat`: For the header, the start/stop and reset buttons, and the manual control readouts.
- `error/#`, `ui/start`, `controller/command/start`, `controller/command/stop` and `controller/command/reset`: For the event log.

And publishes to:
- `ui/start` and `ui/stop`: To start and stop experiments.
- `ui/reset`: To reset the instruments and setpoint controllers.
- `error/ui`: If the experiment settings are invalid when starting an experiment.

## Configuration
The UI reads `comodo.yaml` from `/app/comodo.yaml`, and the following environment variables:
- `MQTT_HOST`, `MQTT_USER` and `MQTT_PASS`: The MQTT broker and its credentials.
- `GRAFANA_HOST`: The host of Grafana, as seen from the browser, used to embed the default dashboard.
  Set from `DATA_HOST` (or `localhost` if empty) in the main [`compose.yaml`](../compose.yaml).
- `GRAFANA_DASHBOARD_URL`: [optional] Overrides the URL of the embedded dashboard.
- `UI_DATA_DIR`: [optional] Where saved settings are stored. Defaults to `/ui_data`.

## Code structure
- [`app.py`](app.py): Creates the Dash app, the navigation and the page routing, and starts the MQTT listeners.
- [`src/`](src/): One module per part of the UI:
  - `top_matter.py`: The header.
  - `main_window.py` and `plot.py`: The timeline page and its graph.
  - `instrument_setup.py`, `spc_setup.py` and `experiment_config.py`: The instruments, PID controllers and global pages.
  - `saved_configs.py` and `saved_selector.py`: Saving and loading settings, and the bar on each settings page.
  - `control_window.py`: The experiment control page.
  - `graph_view.py`: The data monitor page.
  - `log_book.py` and `log_window.py`: The event log, and its page.
  - `heartbeats.py`: Keeps the latest heartbeats received over MQTT, for the other modules to read.
  - `config_loader.py`: The defaults for each page, from `comodo.yaml`.

## Running tests

From the `ui/` directory, run:
```shell
docker compose up --build
```

To check the coverage report after the tests have run:
```shell
xdg-open $(docker volume inspect ui-tests_memory -f '{{ .Mountpoint }}')/htmlcov/class_index.html
```
