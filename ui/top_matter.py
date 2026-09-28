from dash import html, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime
import pytz

import heartbeats as hb

# Display name and card/badge colour of each state reported in the heartbeats
CONTROLLER_STATES = {
    "idle": ("Idle", "primary"),
    "validating": ("Validating", "info"),
    "starting": ("Starting", "warning"),
    "awaiting_instruments": ("Awaiting Instruments", "warning"),
    "ready": ("Ready", "warning"),
    "running": ("Running", "success"),
    "stopping": ("Stopping", "warning"),
    "error": ("Error", "danger"),
}
INSTRUMENT_STATES = {
    "initialising": ("Initialising", "secondary"),
    "awaiting_experiment": ("Awaiting Experiment", "info"),
    "running": ("Running", "success"),
    "error": ("Error", "danger"),
}
SPC_STATES = {
    "idle": ("Idle", "secondary"),
    "adjusting": ("Adjusting", "success"),
    "ready": ("Ready", "success"),
    "error": ("Error", "danger"),
}
NO_HEARTBEAT = ("No heartbeat", "danger")
LOST_HEARTBEAT = ("Heartbeat lost", "danger")


def status_item(item_name):
    status_item = dbc.Col(
        [
            dbc.Row(html.H3(item_name)),
            dbc.Row(html.H4(f"{item_name} status")),
        ]
    )
    return status_item


def get_status_card(header, title, status, id):
    card = dbc.Card(
        [
            dbc.CardHeader(header),
            dbc.CardBody(html.H4(title, className="card-title", id=f"{id}-title")),
        ],
        color=status,
        inverse=True,
        id=id,
    )
    return card


def get_header_bar():
    header_bar = dbc.CardGroup(
        [
            dbc.Card(
                [
                    dbc.CardHeader(""),
                    dbc.CardBody(
                        [
                            html.H1("Comodo Lab", className="card-title"),
                            html.P(
                                "Status updated:\nnever",
                                id="status-updated",
                                className="text-end",
                                style={"whiteSpace": "pre-line"},
                            ),
                        ]
                    ),
                ],
                color="primary",
                inverse=True,
            ),
            get_status_card(
                "Control System Status",
                NO_HEARTBEAT[0],
                NO_HEARTBEAT[1],
                "controller_status",
            ),
            get_status_card(
                "Experiment ID",
                "Awaiting Experiment",
                "primary",
                "experiment_id",
            ),
            dbc.Card(
                [
                    dbc.CardHeader("Instruments"),
                    # Status column as wide as the widest badge, names in the rest
                    dbc.CardBody(
                        id="instruments_status-list",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "max-content 1fr",
                            "gap": "0.25rem 0.5rem",
                            "alignItems": "center",
                        },
                    ),
                ],
                color="primary",
                inverse=True,
                id="instruments_status",
                # Twice as wide as the other cards, to fit setpoint controller names
                style={"flex": "2 1 0"},
            ),
        ],
        className="mb-1",
    )
    return header_bar


def format_time(epoch, timezone):
    try:
        tz = pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc
    return datetime.fromtimestamp(epoch, tz).strftime("%Y-%m-%d %H:%M:%S")


def get_state(data, topic, states, get_value):
    """
    Returns the display name and colour of the state in the latest heartbeat on topic.
    """
    heartbeat = data["heartbeats"].get(topic)
    if heartbeat is None:
        return NO_HEARTBEAT
    if topic in data["stale"]:
        return LOST_HEARTBEAT
    value = get_value(heartbeat["payload"])
    return states.get(value, (f"Unknown ({value})", "secondary"))


@callback(
    Output("heartbeat-store", "data"),
    Input("interval-short", "n_intervals"),
    State("heartbeat-store", "data"),
)
def refresh_heartbeats(n_intervals, current):
    """
    Copies the heartbeats received over MQTT to the browser,
    only when a new one has arrived or one has gone quiet.
    """
    data = hb.snapshot()
    if (
        current
        and data["counter"] == current["counter"]
        and data["stale"] == current["stale"]
    ):
        raise PreventUpdate
    return data


@callback(
    Output("controller_status-title", "children"),
    Output("controller_status", "color"),
    Output("experiment_id-title", "children"),
    Output("experiment_id", "color"),
    Input("heartbeat-store", "data"),
    prevent_initial_call=True,
)
def update_controller_cards(data):
    """
    Updates the controller status and experiment ID cards from the controller heartbeat.
    """
    title, color = get_state(
        data, hb.CONTROLLER_TOPIC, CONTROLLER_STATES, lambda p: p.get("state")
    )
    heartbeat = data["heartbeats"].get(hb.CONTROLLER_TOPIC)
    if heartbeat is None or hb.CONTROLLER_TOPIC in data["stale"]:
        return title, color, "Awaiting Experiment", "primary"

    experiment_id = heartbeat["payload"].get("config", {}).get("experiment_id")
    if experiment_id is None:
        return title, color, "Awaiting Experiment", "primary"
    return title, color, experiment_id, "success"


@callback(
    Output("status-updated", "children"),
    Input("heartbeat-store", "data"),
    State("timezone-store", "data"),
    prevent_initial_call=True,
)
def update_status_time(data, timezone):
    """
    Shows when the most recent heartbeat was received.
    """
    received = [heartbeat["received"] for heartbeat in data["heartbeats"].values()]
    if not received:
        return "\nStatus updated:\nnever"
    return f"\nStatus updated:\n{format_time(max(received), timezone)}"


@callback(
    Output("instruments_status-list", "children"),
    Input("heartbeat-store", "data"),
    prevent_initial_call=True,
)
def update_instruments_card(data):
    """
    Lists the instruments and setpoint controllers with the state in their latest heartbeat.
    """
    rows = []
    for source in data["sources"]:
        if source["kind"] == "spc":
            # Setpoint controllers report their state as an object
            name, color = get_state(
                data,
                source["topic"],
                SPC_STATES,
                lambda p: (p.get("state") or {}).get("status"),
            )
        else:
            name, color = get_state(
                data, source["topic"], INSTRUMENT_STATES, lambda p: p.get("state")
            )
        # Grid cells: the badges stretch to the width of the status column
        rows.append(dbc.Badge(name, color=color))
        rows.append(html.Span(source["label"]))
    return rows
