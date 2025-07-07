from dash import html, callback, Output, Input, State
import dash_bootstrap_components as dbc
from utils.influx_query import query_influxdb_params


def status_item(item_name):
    status_item = dbc.Col([
        dbc.Row(html.H3(item_name)),
        dbc.Row(html.H4(f"{item_name} status"))
    ])
    return status_item

def get_status_card(header, title, text, status, id):
    card = dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody([
            html.H4(title, className="card-title", id=f"{id}-title"),
            html.P(text, className="card-text"),
        ])
    ], color=status, inverse=True, id=id)
    return card

def get_header_bar():
    header_bar = dbc.CardGroup([
        dbc.Card([
            dbc.CardHeader(""),
            dbc.CardBody([
                html.H1("Comodo Lab", className="card-title"),
            ])
        ], color="primary", inverse=True),
        get_status_card("Control System Status", "bad", "15:00:01", "danger", "controller_status"),
        get_status_card("Experiment ID", "ABC-123", "14:44:24", "primary", "experiment_id"),
        get_status_card("Adjusting", "t_left,t_right", "15:00:01", "success", "adjusting_status"),
    ])
    return header_bar


@callback(
    Output("controller_status-title", "title"),
    Output("controller_status", "color"),
    Input("controller_interval", "n_intervals"),
    prevent_initial_call=True
)
def update_header_status(n_intervals):
    """
    Updates the header bar with the latest status.
    """
    try:
        status = query_influxdb_params(
            fields=["status"],
            topics=["heartbeat/controller"],
            start="-1m",
            aggregate="last"
        )[-1].get_value()
    except Exception as e:
        print(f"Error querying status: {e}")

    if status == "awaiting_sensors":
        return "Awaiting Sensors", "warning"
    if status == "end":
        return "Experiment Ended", "light"
    if status == "idle":
        return "Idle", "secondary"
    if status == "ready":
        return "Ready", "info"
    if status == "running":
        return "Running", "success"
    if status == "starting":
        return "Starting", "primary"
    if status == "error":
        return "Error", "danger"

    print(f"Unknown status: {status}")

    return "Unknown Status", "primary"
