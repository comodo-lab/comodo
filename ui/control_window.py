from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    no_update,
    ctx,
    MATCH,
    ALL,
)
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import json
import uuid

from utils.mqtt_clients import MQTTPublisher
from utils.influx_query import query_influxdb_params


def get_control_panel(params=[]):
    card_cols = [dbc.Col(get_instrument_card(p), md=4, sm=6) for p in params]

    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-play-fill me-1"), "Start Experiment"],
                            id="submit-experiment",
                            color="success",
                            n_clicks=0,
                        ),
                        className="d-grid",
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-pause-fill me-1"), "Pause"],
                            id="pause-resume-btn",
                            color="warning",
                            n_clicks=0,
                            disabled=True,
                        ),
                        className="d-grid",
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="bi bi-sliders me-1"), "Apply Override"],
                            id="apply-override-btn",
                            color="danger",
                            n_clicks=0,
                            disabled=True,
                        ),
                        className="d-grid",
                        md=3,
                    ),
                    dbc.Col(
                        dbc.Badge(
                            "—",
                            id="controller-status-badge",
                            color="secondary",
                            className="d-flex align-items-center fs-6 p-2",
                        ),
                        md=3,
                        className="d-flex align-items-center",
                    ),
                ],
                className="g-2 mb-3 align-items-center",
            ),
            html.Div(
                dbc.Row(card_cols, className="g-3"),
                id="override-wrapper",
                style={"pointerEvents": "none", "opacity": "0.65"},
            ),
            html.P(
                "Pause the experiment to enable manual override.",
                id="override-hint",
                className="text-muted mt-2 small",
            ),
        ],
        fluid=True,
    )


def get_instrument_card(param):
    name = param["name"]
    label = " ".join(w.capitalize() for w in name.split("_"))
    return dbc.Card(
        [
            dbc.CardHeader(html.Strong(label)),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Small("Current", className="text-muted d-block"),
                                    html.H4("—", id={"type": "live-value", "index": name}),
                                ]
                            ),
                            dbc.Col(
                                [
                                    html.Small("Setpoint", className="text-muted d-block"),
                                    html.H4("—", id={"type": "live-setpoint", "index": name}),
                                ]
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.Hr(className="my-2"),
                    dbc.Input(
                        id={"type": "manual-input", "index": name},
                        type="number",
                        min=param.get("min", 0),
                        max=param.get("max", 100),
                        step=param.get("step", 1),
                        placeholder="Override value…",
                    ),
                ]
            ),
        ]
    )


@callback(
    Output("hidden-div", "children"),
    Input("submit-experiment", "n_clicks"),
    State("experiment-designer-store", "data"),
    State("instrument-store", "data"),
    State("experiment-config-store", "data"),
    prevent_initial_call=True,
)
def start_experiment(n_clicks, table_data, instruments, exp_config):
    if not n_clicks or not table_data:
        raise PreventUpdate

    experiment_id = str(uuid.uuid4())[:8]
    resolution = 1
    if exp_config:
        for cfg in exp_config:
            if cfg.get("name") == "resolution":
                resolution = cfg["value"]

    payload = {
        "uid": experiment_id,
        "config": {"resolution": resolution, "instruments": instruments},
        "experiment": table_data,
    }
    MQTTPublisher.get_instance().publish("ui/start", json.dumps(payload).encode("utf-8"))
    return None


@callback(
    Output("controller-status-badge", "children"),
    Output("controller-status-badge", "color"),
    Output("pause-resume-btn", "children"),
    Output("pause-resume-btn", "color"),
    Output("pause-resume-btn", "disabled"),
    Output("apply-override-btn", "disabled"),
    Output("override-wrapper", "style"),
    Output("override-hint", "children"),
    Output("submit-experiment", "disabled"),
    Input("interval", "n_intervals"),
    prevent_initial_call=True,
)
def update_control_state(n_intervals):
    disabled_style = {"pointerEvents": "none", "opacity": "0.65"}
    enabled_style = {}
    pause_btn = [html.I(className="bi bi-pause-fill me-1"), "Pause"]
    resume_btn = [html.I(className="bi bi-play-fill me-1"), "Resume"]
    hint_inactive = "Pause the experiment to enable manual override."
    hint_active = "Override active — inputs are live."

    try:
        status = query_influxdb_params(
            fields=["status"],
            topics=["heartbeat/controller"],
            start="-1m",
            aggregate="last",
        )[-1].get_value()
    except Exception:
        return (
            "Unknown", "secondary",
            pause_btn, "warning", True,
            True, disabled_style, hint_inactive,
            False,
        )

    status_map = {
        "idle":                 ("Idle", "secondary"),
        "validating":           ("Validating", "info"),
        "starting":             ("Starting", "primary"),
        "awaiting_instruments": ("Awaiting Instruments", "warning"),
        "ready":                ("Ready", "info"),
        "running":              ("Running", "success"),
        "paused":               ("Paused", "warning"),
        "stopping":             ("Stopping", "danger"),
        "error":                ("Error", "danger"),
    }
    badge_text, badge_color = status_map.get(
        status, (status.replace("_", " ").capitalize(), "secondary")
    )

    is_running = status == "running"
    is_paused = status == "paused"
    is_idle = status == "idle"

    btn_label = pause_btn if is_running else resume_btn
    btn_color = "warning" if is_running else "success"
    btn_disabled = not (is_running or is_paused)
    override_disabled = not (is_paused or is_idle)
    wrapper_style = enabled_style if (is_paused or is_idle) else disabled_style
    hint = hint_active if (is_paused or is_idle) else hint_inactive
    submit_disabled = not is_idle

    return (
        badge_text, badge_color,
        btn_label, btn_color, btn_disabled,
        override_disabled, wrapper_style, hint,
        submit_disabled,
    )


@callback(
    Output({"type": "live-value", "index": MATCH}, "children"),
    Output({"type": "live-setpoint", "index": MATCH}, "children"),
    Input("interval", "n_intervals"),
    State({"type": "live-value", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def update_live_readings(n_intervals, component_id):
    name = component_id["index"]
    try:
        # name is "instrument_id/variable_name"
        base_id = name.split("/")[0]
        
        # Setpoint is published to instrument/{base_id}/setpoint with field {base_id}
        setpoint_results = query_influxdb_params(
            fields=[base_id],
            topics=[f"instrument/{base_id}/setpoint"],
            start="-1m",
            aggregate="last",
        )
        setpoint = setpoint_results[-1].get_value() if setpoint_results else None
        
        # Measurement is published to measurement/{base_id}/{variable} with field "value"
        actual_results = query_influxdb_params(
            fields=["value"],
            topics=[f"measurement/{name}"],
            start="-1m",
            aggregate="last",
        )
        actual = actual_results[-1].get_value() if actual_results else None
        
        if not actual_results and n_intervals % 5 == 0:
             print(f"DEBUG: No actual results found in InfluxDB for measurement/{name} in the last 1m")
        if not setpoint_results and n_intervals % 5 == 0:
             print(f"DEBUG: No setpoint results found in InfluxDB for instrument/{base_id}/setpoint in the last 1m")

        setpoint_display = f"{setpoint:.3g}" if setpoint is not None else "—"
        actual_display = f"{actual:.3g}" if actual is not None else "—"
        
        return actual_display, setpoint_display
    except Exception as e:
        print(f"ERROR in update_live_readings for {name}: {e}")
        return no_update, no_update


@callback(
    Output("hidden-div", "children", allow_duplicate=True),
    Input("pause-resume-btn", "n_clicks"),
    prevent_initial_call=True,
)
def pause_resume_experiment(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    try:
        status = query_influxdb_params(
            fields=["status"],
            topics=["heartbeat/controller"],
            start="-1m",
            aggregate="last",
        )[-1].get_value()
        uid = query_influxdb_params(
            fields=["experiment"],
            topics=["heartbeat/controller"],
            start="-1m",
            aggregate="last",
        )[-1].get_value()
    except Exception:
        raise PreventUpdate

    client = MQTTPublisher.get_instance()
    if status == "running":
        client.publish("ui/pause", json.dumps({"uid": uid}))
    elif status == "paused":
        client.publish("ui/resume", json.dumps({"uid": uid}))
    return None


@callback(
    Output("hidden-div", "children", allow_duplicate=True),
    Input("apply-override-btn", "n_clicks"),
    State({"type": "manual-input", "index": ALL}, "value"),
    State({"type": "manual-input", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def apply_override(n_clicks, values, input_ids):
    if not n_clicks:
        raise PreventUpdate
    try:
        uid_record = query_influxdb_params(
            fields=["experiment"],
            topics=["heartbeat/controller"],
            start="-1m",
            aggregate="last",
        )
        uid = uid_record[-1].get_value() if uid_record else "manual"
    except Exception:
        uid = "manual"

    if uid is None:
        uid = "manual"

    setpoints = {
        iid["index"]: v
        for iid, v in zip(input_ids, values)
        if v is not None
    }
    if not setpoints:
        raise PreventUpdate

    MQTTPublisher.get_instance().publish(
        "ui/setpoint", json.dumps({"uid": uid, "setpoints": setpoints})
    )
    return None
