from dash import html, callback, Output, Input, State
import dash_bootstrap_components as dbc
from utils.influx_query import query_influxdb_params


def status_item(item_name):
    status_item = dbc.Col([
        dbc.Row(html.H3(item_name)),
        dbc.Row(html.H4(f"{item_name} status"))
    ])
    return status_item


def get_header_bar(n_intervals):
    header_bar = dbc.Container([
        dbc.Row(html.H1("Comodo-Lab")),
        dbc.Row(
            dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Control System Status"),
                        html.Th("Experiment ID"),
                        html.Th("Adjusting"),
                    ]),
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td("Unknown", id="status"),
                        html.Td("ABC-123"),
                        html.Td("Temp1, Temp2")
                    ]),
                ]),
            ]),
        ),
        ],

        fluid=True,
        className="p-4 bg-light rounded",
    )

    return header_bar


@callback(
    Output("status", "children"),
    Input("interval", "n_intervals"),
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
        status = "unknown"

    return status.capitalize()
