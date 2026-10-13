from dash import (
    Dash,
    dash_table,
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    no_update,
    ctx,
    MATCH,
    clientside_callback,
)
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.express as px
import uuid
import json
import time
import pytz


import dash_ag_grid as dag
import dash_daq as daq

import pandas as pd
import plotly.graph_objects as go

from utils.mqtt_clients import MQTTPublisher
from utils.influx_query import query_influxdb_params
import saved_configs as sc
import heartbeats as hb
import instrument_setup as ins

# Seconds to wait for the controller state to change after a click, before giving up
CLICK_TIMEOUT = 5


def get_control_panel(params=[]):
    layout = html.Div(
        [
            dbc.Button("Start experiment", color="success", id="experiment-button"),
            dcc.Store(id="experiment-button-click"),
            get_manual_panel(params=params),
        ],
        className="d-grid gap-2",
    )
    return layout


# Disables the button in the browser as soon as it is clicked, to prevent double clicks.
# It is enabled again by update_experiment_button once the controller state changes.
clientside_callback(
    "function(n_clicks) { return true; }",
    Output("experiment-button", "disabled", allow_duplicate=True),
    Input("experiment-button", "n_clicks"),
    prevent_initial_call=True,
)


@callback(
    Output("experiment-button", "children", allow_duplicate=True),
    Output("experiment-button-click", "data"),
    Output("hidden-div", "children"),
    Output("experiment-meta-store", "data", allow_duplicate=True),
    Output("instruments-meta-store", "data", allow_duplicate=True),
    Output("config-meta-store", "data", allow_duplicate=True),
    Input("experiment-button", "n_clicks"),
    State("experiment-button", "value"),
    State("heartbeat-store", "data"),
    State("experiment-designer-store", "data"),
    State("instrument-store", "data"),
    State("experiment-config-store", "data"),
    State("experiment-meta-store", "data"),
    State("instruments-meta-store", "data"),
    State("config-meta-store", "data"),
    prevent_initial_call=True,
)
def start_or_stop_experiment(n_clicks, experiment_id, heartbeats, *start_states):
    """
    Stops the running experiment if there is one, otherwise starts a new one.
    """
    if not n_clicks:
        raise PreventUpdate
    click = {"state": controller_state(heartbeats), "time": time.time()}
    if experiment_id:
        client = MQTTPublisher.get_instance()
        client.publish("ui/stop", json.dumps({"experiment_id": experiment_id}))
        return busy("Stopping experiment"), click, None, no_update, no_update, no_update
    return busy("Starting experiment"), click, *start_experiment(*start_states)


def start_experiment(
    table_data, instruments, exp_config, exp_meta, inst_meta, config_meta
):
    # Group the instrument setup rows into the live config of each instrument
    try:
        instruments_config = ins.to_instrument_config(instruments)
    except ValueError as e:
        print(f"Invalid instrument setup: {e}")
        MQTTPublisher.get_instance().publish(
            "error/ui", json.dumps({"code": "instrument_setup", "message": str(e)})
        )
        return None, no_update, no_update, no_update

    # Save any unsaved changes, so the run can link to the versions used
    files = {}
    metas = {}
    try:
        for kind, data, meta in (
            ("experiment", table_data, exp_meta),
            ("instruments", instruments, inst_meta),
            ("config", exp_config, config_meta),
        ):
            files[kind], metas[kind] = sc.save_if_changed(kind, data, meta)
    except OSError as e:
        print(f"Error saving experiment files: {e}")

    # Prepare data for transmission
    temp_id = str(uuid.uuid4())[:8]

    for config in exp_config:
        if config["name"] == "resolution":
            resolution = config["value"]

    if resolution is None:
        print("No resolution set, defaulting to 1 second.")
        resolution = 1

    experiment_definition = [
        {key: value for key, value in row.items() if key != "id"} for row in table_data
    ]
    experiment_config = {
        "temp_id": temp_id,
        "config": {"resolution": resolution, "instruments": instruments_config},
        "experiment_definition": experiment_definition,
    }
    json_data = json.dumps(experiment_config).encode("utf-8")

    print(f"Data: {json_data}")
    # Publish data
    client = MQTTPublisher.get_instance()
    client.publish("ui/start", json_data)

    if len(files) == len(sc.KINDS):
        try:
            sc.save_run(temp_id, files)
        except OSError as e:
            print(f"Error saving run file: {e}")
    return (
        None,
        metas.get("experiment", no_update),
        metas.get("instruments", no_update),
        metas.get("config", no_update),
    )


@callback(
    Output("experiment-button", "children"),
    Output("experiment-button", "color"),
    Output("experiment-button", "value"),
    Output("experiment-button", "disabled"),
    Input("heartbeat-store", "data"),
    State("experiment-button-click", "data"),
)
def update_experiment_button(data, click):
    """
    Sets the button from the controller heartbeat: start when idle, stop when there is
    an experiment_id, and disabled while the controller is validating or stopping.
    After a click, the button stays busy until the controller state changes,
    or CLICK_TIMEOUT passes (e.g. the controller rejected the request).
    """
    current = controller_state(data)
    if (
        click
        and (time.time() - click["time"] < CLICK_TIMEOUT)
        and ((current is None) or (list(current) == click["state"]))
    ):
        raise PreventUpdate

    if current is None:
        return "No controller heartbeat", "secondary", None, True
    state, experiment_id = current
    if state == "idle":
        return "Start experiment", "success", None, False
    if state == "validating":
        return busy("Validating experiment"), "success", None, True
    if state == "stopping":
        return busy("Stopping experiment"), "danger", None, True
    if experiment_id:
        return f"Stop experiment {experiment_id}", "danger", experiment_id, False
    return f"Controller {state}", "secondary", None, True


def busy(text):
    return [dbc.Spinner(size="sm", spinner_class_name="me-2"), text]


def controller_state(data):
    """
    Returns the state and experiment_id in the latest controller heartbeat,
    or None if there is no recent heartbeat.
    """
    heartbeat = (data or {}).get("heartbeats", {}).get(hb.CONTROLLER_TOPIC)
    if heartbeat is None or hb.CONTROLLER_TOPIC in data["stale"]:
        return None
    payload = heartbeat["payload"]
    return payload.get("state"), payload.get("config", {}).get("experiment_id")


def get_manual_panel(params=[]):
    """
    Creates the control window for the experiment designer.
    """
    if not params:
        raise ValueError(
            "Parameter list cannot be empty. Please provide at least one parameter."
        )

    control_rows = [
        dbc.Row(html.H2("Manual Control Window")),
        dbc.Row(html.Hr()),
        dbc.Row(html.P("Last update: N/A", id="control-last-update")),
    ]

    for param in params:
        param_name = param["name"]
        param_min = param.get("min", 0)
        param_max = param.get("max", 100)
        param_step = param.get("step", 1)

        control_rows.append(
            html.H4(
                f"Control: {' '.join(w.capitalize() for w in param_name.split('_'))}"
            )
        )
        control_rows.append(
            get_control_component(
                param_name=param_name,
                min_val=param_min,
                max_val=param_max,
                step=param_step,
            )
        )

    # Define the layout of the control window
    control_window = dbc.Container(control_rows, fluid=True)

    return control_window


def get_control_component(param_name=None, min_val=0, max_val=100, step=1):
    """
    Returns the control component for the experiment designer.
    Includes a slider and a readout for current setpoint and actual value.
    """
    if param_name is None:
        return html.Div(
            [
                html.H4("No Parameter Selected"),
            ],
            id="control-component-no-param",
        )

    control_component = dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Slider(
                            id={"type": "control-slider", "index": param_name},
                            min=min_val,
                            max=max_val,
                            step=step,
                            value=(min_val + max_val) // 2,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                    ),
                    dbc.Col(
                        daq.Gauge(
                            id={"type": "control-gauge", "index": param_name},
                            min=min_val,
                            max=max_val,
                            value=(min_val + max_val) // 2,
                        ),
                        width=4,
                    ),
                ]
            )
        ]
    )

    return control_component


@callback(
    Output({"type": "control-gauge", "index": MATCH}, "value"),
    Output({"type": "control-slider", "index": MATCH}, "value"),
    # Output("control-last-update", "children"),
    Input("interval", "n_intervals"),
    State({"type": "control-slider", "index": MATCH}, "id"),
    State("timezone-store", "data"),
)
def update_control_component(n_intervals, slider_id, timezone):
    """
    Updates the control component based on the selected parameter.
    """
    # Extract the parameter name from the slider's id
    param_name = slider_id["index"]

    try:
        user_tz = pytz.timezone(timezone)
        time = pytz.datetime.datetime.now(user_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error getting current time: {e}")
        time = "N/A"

    # Query setpoint and actual value for the parameter
    try:
        setpoint_results = query_influxdb_params(
            fields=["value"],
            topics=[f"instruments/{param_name}/setpoint"],
            start="-1m",
            aggregate="last",
        )
        actual_results = query_influxdb_params(
            fields=["value"],
            topics=[f"instruments/{param_name}/measurement"],
            start="-1m",
            aggregate="last",
        )
        if not setpoint_results or not actual_results:
            return no_update, no_update
        setpoint = setpoint_results[-1].get_value()

        actual_value = actual_results[-1].get_value()
    except Exception as e:
        if "list index out of range" not in str(e):
            print(f"Error querying InfluxDB for {param_name}: {e}")
        return no_update, no_update  # , time

    # Update the gauge and slider values
    return actual_value, setpoint  # , time
