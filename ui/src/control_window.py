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


import dash_ag_grid as dag
import dash_daq as daq

import pandas as pd
import plotly.graph_objects as go

from utils.mqtt_clients import MQTTPublisher
import src.saved_configs as sc
import src.heartbeats as hb
import src.instrument_setup as ins
import src.spc_setup as spc

# Seconds to wait for the controller state to change after a click, before giving up
CLICK_TIMEOUT = 5

RESET_MESSAGE = (
    "Reset all instruments and setpoint controllers to their default setpoints?\n\n"
    "This also clears any safe stops, so make sure whatever caused them has been fixed."
)


def get_control_panel(params=[]):
    toggle_label, toggle_color = manual_toggle(False)
    layout = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            content("Start experiment", "play-circle"),
                            color="success",
                            id="experiment-button",
                        ),
                        width=9,
                        className="d-grid",
                    ),
                    dbc.Col(
                        [
                            dbc.Button(
                                # Disabled until instruments support manual control
                                toggle_label
                                + [
                                    html.Small(
                                        "(coming soon...)",
                                        className="text-muted",
                                        style={"textTransform": "none"},
                                    )
                                ],
                                color=toggle_color,
                                id="manual-control-toggle",
                                n_clicks=0,
                                disabled=True,
                            ),
                            # Enabled by update_reset_button while the controller is idle
                            dbc.Button(
                                content(
                                    "Reset", "arrow-counterclockwise", SMALL_ICON_SIZE
                                ),
                                color="warning",
                                id="reset-button",
                                disabled=True,
                            ),
                            dcc.ConfirmDialog(
                                id="reset-confirm", message=RESET_MESSAGE
                            ),
                        ],
                        width=3,
                        className="d-grid gap-2",
                    ),
                ],
                className="g-2",
            ),
            dcc.Store(id="experiment-button-click"),
            # Hidden rather than removed, so its controls keep updating
            dbc.Collapse(
                get_manual_panel(params=params),
                id="manual-control-collapse",
                is_open=False,
            ),
        ],
        className="d-grid gap-2",
    )
    return layout


def manual_toggle(is_open):
    """Returns the (content, color) of the manual control toggle."""
    if is_open:
        return content("Hide Manual Control", "sliders", SMALL_ICON_SIZE), "warning"
    return content("Take Manual Control", "sliders", SMALL_ICON_SIZE), "light"


@callback(
    Output("manual-control-collapse", "is_open"),
    Output("manual-control-toggle", "children"),
    Output("manual-control-toggle", "color"),
    Input("manual-control-toggle", "n_clicks"),
    State("manual-control-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_manual_control(n_clicks, is_open):
    # Fires when the tab is rendered, as prevent_initial_call does not apply
    # to inputs inserted by another callback (render_page)
    if not n_clicks:
        raise PreventUpdate
    return not is_open, *manual_toggle(not is_open)


@callback(
    Output("reset-button", "disabled"),
    Input("heartbeat-store", "data"),
)
def update_reset_button(data):
    """
    Enables the reset button only while the controller is idle,
    as it doesn't reset a running experiment (it has to be stopped first).
    """
    current = hb.controller_state(data)
    return current is None or current[0] != "idle"


@callback(
    Output("reset-confirm", "displayed"),
    Input("reset-button", "n_clicks"),
    prevent_initial_call=True,
)
def confirm_reset(n_clicks):
    """Asks for confirmation before resetting, as it moves the actuators and clears safe stops."""
    # Fires when the tab is rendered (see toggle_manual_control)
    if not n_clicks:
        raise PreventUpdate
    return True


@callback(
    Output("reset-button", "disabled", allow_duplicate=True),
    Input("reset-confirm", "submit_n_clicks"),
    prevent_initial_call=True,
)
def reset(submit_n_clicks):
    """
    Asks the controller to reset the instruments and setpoint controllers.
    The button is disabled until the next heartbeat update, to prevent double clicks.
    """
    if not submit_n_clicks:
        raise PreventUpdate
    MQTTPublisher.get_instance().publish("ui/reset", json.dumps({"source": "ui"}))
    return True


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
    Output("spcs-meta-store", "data", allow_duplicate=True),
    Input("experiment-button", "n_clicks"),
    State("experiment-button", "value"),
    State("heartbeat-store", "data"),
    State("experiment-designer-store", "data"),
    State("instrument-store", "data"),
    State("experiment-config-store", "data"),
    State("spc-store", "data"),
    State("experiment-meta-store", "data"),
    State("instruments-meta-store", "data"),
    State("config-meta-store", "data"),
    State("spcs-meta-store", "data"),
    prevent_initial_call=True,
)
def start_or_stop_experiment(n_clicks, experiment_id, heartbeats, *start_states):
    """
    Stops the running experiment if there is one, otherwise starts a new one.
    """
    if not n_clicks:
        raise PreventUpdate
    click = {"state": hb.controller_state(heartbeats), "time": time.time()}
    if experiment_id:
        client = MQTTPublisher.get_instance()
        client.publish("ui/stop", json.dumps({"experiment_id": experiment_id}))
        return (
            busy("Stopping experiment"),
            click,
            None,
            *[no_update] * len(sc.KINDS),
        )
    return busy("Starting experiment"), click, *start_experiment(*start_states)


def start_experiment(
    table_data,
    instruments,
    exp_config,
    spcs,
    exp_meta,
    inst_meta,
    config_meta,
    spcs_meta,
):
    # Group the instrument setup rows into the live config of each instrument,
    # which needs a tolerance for every variable with setpoints in the experiment
    try:
        instruments_config = ins.to_instrument_config(instruments)
        ins.check_tolerances(instruments_config, ins.experiment_variables(table_data))
    except ValueError as e:
        print(f"Invalid instrument setup: {e}")
        MQTTPublisher.get_instance().publish(
            "error/ui", json.dumps({"code": "instrument_setup", "message": str(e)})
        )
        return None, *[no_update] * len(sc.KINDS)
    # The PID gains of each setpoint controller, checked by the controller in their heartbeats
    try:
        spcs_config = spc.to_spc_config(spcs)
    except ValueError as e:
        print(f"Invalid setpoint controller setup: {e}")
        MQTTPublisher.get_instance().publish(
            "error/ui", json.dumps({"code": "spc_setup", "message": str(e)})
        )
        return None, *[no_update] * len(sc.KINDS)

    # Save any unsaved changes, so the run can link to the versions used
    files = {}
    metas = {}
    try:
        for kind, data, meta in (
            ("experiment", table_data, exp_meta),
            ("instruments", instruments, inst_meta),
            ("config", exp_config, config_meta),
            ("spcs", spcs, spcs_meta),
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
        "config": {
            "resolution": resolution,
            "instruments": instruments_config,
            "spcs": spcs_config,
        },
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
        metas.get("spcs", no_update),
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
    current = hb.controller_state(data)
    if (
        click
        and (time.time() - click["time"] < CLICK_TIMEOUT)
        and ((current is None) or (list(current) == click["state"]))
    ):
        raise PreventUpdate

    if current is None:
        no_heartbeat = content("No controller heartbeat", "exclamation-circle")
        return no_heartbeat, "secondary", None, True
    state, experiment_id = current
    if state == "idle":
        return content("Start experiment", "play-circle"), "success", None, False
    if state == "validating":
        return busy("Validating experiment"), "success", None, True
    if state == "stopping":
        return busy("Stopping experiment"), "danger", None, True
    if experiment_id:
        return (
            content(f"Stop experiment {experiment_id}", "stop-circle"),
            "danger",
            experiment_id,
            False,
        )
    return content(f"Controller {state}", "hourglass-split"), "secondary", None, True


# Size of the icons in the experiment and manual control buttons
ICON_SIZE = "3.5rem"
SMALL_ICON_SIZE = "2rem"


def content(text, icon, size=ICON_SIZE):
    """Button content: a Bootstrap icon, with the text below it."""
    return [
        html.I(className=f"bi bi-{icon} d-block my-2", style={"fontSize": size}),
        html.Div(text),
    ]


def busy(text):
    spinner = dbc.Spinner(
        spinner_style={"width": ICON_SIZE, "height": ICON_SIZE},
        spinner_class_name="my-2",
    )
    return [spinner, html.Div(text)]


def get_manual_panel(params=[]):
    """
    Creates the control window for the experiment designer.
    """
    if not params:
        raise ValueError(
            "Parameter list cannot be empty. Please provide at least one parameter."
        )

    control_rows = [
        dbc.Row(html.Hr(className="border-warning border-2 opacity-100 mt-2")),
        dbc.Row(html.H2("Manual Control Window", className="mt-2")),
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


def manual_values(data, param_name):
    """
    Returns the (measurement, setpoint) of param_name (instrument/variable) from the
    heartbeats in the heartbeat-store, or None for each one not available.
    The setpoint comes from the setpoint controller driving the variable, if any,
    as the instrument only reports setpoints of its actuators.
    """
    heartbeats = (data or {}).get("heartbeats", {})
    stale = (data or {}).get("stale", [])
    fresh = {t: hb["payload"] for t, hb in heartbeats.items() if t not in stale}

    instrument, variable = param_name.split("/", 1)
    payload = fresh.get(hb.instrument_topic(instrument), {})
    measurement = payload.get("state", {}).get("measurements", {}).get(variable)
    setpoint = payload.get("setpoints", {}).get(variable)
    for topic, spc_payload in fresh.items():
        if (
            topic.startswith("setpoint_controllers/")
            and spc_payload["config"]["sensor"] == param_name
        ):
            setpoint = spc_payload["setpoints"]["sensor_setpoint"]
    return measurement, setpoint


@callback(
    Output({"type": "control-gauge", "index": MATCH}, "value"),
    Output({"type": "control-slider", "index": MATCH}, "value"),
    Input("heartbeat-store", "data"),
    State({"type": "control-slider", "index": MATCH}, "id"),
)
def update_control_component(data, slider_id):
    """
    Shows the latest measurement (gauge) and setpoint (slider) of the parameter.
    """
    measurement, setpoint = manual_values(data, slider_id["index"])
    return (
        no_update if measurement is None else measurement,
        no_update if setpoint is None else setpoint,
    )
