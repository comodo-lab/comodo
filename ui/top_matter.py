from dash import html, callback, Output, Input, State
import dash_bootstrap_components as dbc
from utils.influx_query import query_influxdb_params
import pytz


def status_item(item_name):
    status_item = dbc.Col(
        [
            dbc.Row(html.H3(item_name)),
            dbc.Row(html.H4(f"{item_name} status")),
        ]
    )
    return status_item


def get_status_card(header, title, text, status, id):
    card = dbc.Card(
        [
            dbc.CardHeader(header),
            dbc.CardBody(
                [
                    html.H4(title, className="card-title", id=f"{id}-title"),
                    html.P(text, className="card-text", id=f"{id}-time"),
                ]
            ),
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
                        ]
                    ),
                ],
                color="primary",
                inverse=True,
            ),
            get_status_card(
                "Control System Status",
                "waiting",
                "15:00:01",
                "warning",
                "controller_status",
            ),
            get_status_card(
                "Experiment ID",
                "Awaiting Experiment",
                "14:44:24",
                "primary",
                "experiment_id",
            ),
            get_status_card(
                "Adjusting", "None", "15:00:01", "primary", "adjusting_status"
            ),
        ]
    )
    return header_bar


@callback(
    Output("controller_status-title", "children"),
    Output("controller_status", "color"),
    Output("controller_status-time", "children"),
    Input("interval", "n_intervals"),
    State("timezone-store", "data"),
    prevent_initial_call=True,
)
def update_header_status(n_intervals, timezone):
    """
    Updates the header bar with the latest status.
    """
    user_tz = pytz.timezone(timezone)

    try:
        result = query_influxdb_params(
            fields=["state"],
            topics=["controller/heartbeat"],
            start="-1m",
            aggregate="last",
        )[-1]
        status = result.get_value()
        iso_timestamp = result.get_time()
        timestamp = iso_timestamp.astimezone(user_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error querying status: {e}")
        return "Unknown Status", "primary", None

    if status == "awaiting_instruments":
        return "Awaiting Instruments", "warning", timestamp
    if status == "end":
        return "Experiment Ended", "light", timestamp
    if status == "idle":
        return "Idle", "primary", timestamp
    if status == "ready":
        return "Ready", "info", timestamp
    if status == "running":
        return "Running", "success", timestamp
    if status == "starting":
        return "Starting", "primary", timestamp
    if status == "error":
        return "Error", "danger", timestamp

    print(f"Unknown status: {status}")

    return "Unknown Status", "primary", timestamp


@callback(
    Output("experiment_id-title", "children"),
    Output("experiment_id", "color"),
    Output("experiment_id-time", "children"),
    Input("interval", "n_intervals"),
    State("timezone-store", "data"),
    prevent_initial_call=True,
)
def update_header_id(n_intervals, timezone):
    """
    Updates the header bar with the latest experiment ID.
    """
    user_tz = pytz.timezone(timezone)

    try:
        result = query_influxdb_params(
            fields=["experiment_id"],
            topics=["controller/heartbeat"],
            start="-1m",
            aggregate="last",
        )[-1]
        id = result.get_value()
        iso_timestamp = result.get_time()
        timestamp = iso_timestamp.astimezone(user_tz).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        if "list index out of range" not in str(e):
            print(f"Error querying id: {e}")
        time = pytz.datetime.datetime.now(user_tz).strftime("%Y-%m-%d %H:%M:%S")
        return "Awaiting Experiment", "primary", time

    return id, "success", timestamp


@callback(
    Output("adjusting_status-title", "children"),
    Output("adjusting_status", "color"),
    Output("adjusting_status-time", "children"),
    Input("interval", "n_intervals"),
    State("instrument-store", "data"),
    State("timezone-store", "data"),
    prevent_initial_call=True,
)
def update_header_id(n_intervals, instruments, timezone):
    """
    Updates the header bar with the variables currently being adjusted.
    """
    user_tz = pytz.timezone(timezone)
    time = pytz.datetime.datetime.now(user_tz).strftime("%Y-%m-%d %H:%M:%S")

    adjusting = []

    if instruments is None:
        return "None Adjusting", "primary", time

    print(f"Checking state of {len(instruments)} instruments...")
    for instrument in instruments:
        instrument_name = instrument["name"]
        try:
            result = query_influxdb_params(
            fields=["state"],
            topics=[f"instruments/{instrument_name}/heartbeat"],
                start="-1m",
                aggregate="last",
            )[-1]
            id = result.get_value()
            if id == "adjusting":
                adjusting.append(instrument_name)
            iso_timestamp = result.get_time()
            timestamp = iso_timestamp.astimezone(user_tz).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Error querying awaiting for {instrument_name}: {e}")
            return "None Adjusting", "primary", time

    if len(adjusting) == 0:
        return "None Adjusting", "primary", timestamp
    else:
        adjusting_str = ", ".join(
            " ".join(instrument.split("_")).capitalize() for instrument in adjusting
        )

    return adjusting_str, "success", timestamp
