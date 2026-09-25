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
)
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.express as px
import uuid
import json
import pytz


import dash_ag_grid as dag
import dash_daq as daq

import pandas as pd
import plotly.graph_objects as go

from utils.mqtt_clients import MQTTPublisher
from utils.influx_query import query_influxdb_params


def get_control_panel(params=[]):
    layout = html.Div(
        [
            dbc.Button("Start experiment", color="success", id="submit-experiment"),
            get_manual_panel(params=params),
        ],
        className="d-grid gap-2",
    )
    return layout


@callback(
    Output("hidden-div", "children"),
    Input("submit-experiment", "n_clicks"),
    State("experiment-designer-store", "data"),
    State("instrument-store", "data"),
    State("experiment-config-store", "data"),
    prevent_initial_call=True,
)
def update_output(n_clicks, table_data, instruments, exp_config):
    if n_clicks == None:
        raise PreventUpdate

    # Prepare data for transmission
    experiment_id = str(uuid.uuid4())[:8]

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
        "id": experiment_id,
        "config": {"resolution": resolution, "instruments": instruments},
        "experiment_definition": experiment_definition,
    }
    json_data = json.dumps(experiment_config).encode("utf-8")

    print(f"Data: {json_data}")
    # Publish data
    client = MQTTPublisher.get_instance()
    client.publish("ui/start", json_data)
    return None


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
    State("instrument-store", "data"),
    State({"type": "control-slider", "index": MATCH}, "id"),
    State("timezone-store", "data"),
)
def update_control_component(n_intervals, instruments, slider_id, timezone):
    """
    Updates the control component based on the selected parameter.
    """
    # Extract the parameter name from the slider's id
    param_name = slider_id["index"]

    # Find the corresponding instrument data
    instrument = next((s for s in instruments if s["name"] == param_name), None)

    try:
        user_tz = pytz.timezone(timezone)
        time = pytz.datetime.datetime.now(user_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error getting current time: {e}")
        time = "N/A"

    if not instrument:
        return no_update, no_update  # , time

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
