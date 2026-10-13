from dash import html, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_ag_grid as dag

import log_book as lb
import top_matter as tm

LOG_PATH = "/log"
# Log tab highlighted while there are errors not yet seen
UNSEEN_STYLE = {"backgroundColor": "var(--bs-danger)", "color": "white"}


def get_log_window():
    """
    Creates a table with the errors published by any component and the experiment
    lifecycle events, newest first. Errors are highlighted.
    """
    column_dicts = [
        {"headerName": "Time", "field": "time", "width": 180, "sort": "desc"},
        {"headerName": "Type", "field": "type", "width": 100},
        {"headerName": "Source", "field": "source", "width": 180},
        {"headerName": "Code", "field": "code", "width": 200},
        {
            "headerName": "Message",
            "field": "message",
            "flex": 1,
            "wrapText": True,
            "autoHeight": True,
            "cellStyle": {"whiteSpace": "pre-wrap", "lineHeight": "1.4"},
        },
    ]
    return html.Div(
        [
            html.P(
                "Errors published by the controller, instruments and other components, "
                "and experiment start and stop messages, since the UI started "
                f"(up to the latest {lb.MAX_ENTRIES}).",
                className="text-muted",
            ),
            dag.AgGrid(
                id="error-log",
                columnDefs=column_dicts,
                rowData=[],
                className="ag-theme-alpine",
                defaultColDef={"resizable": True, "filter": True, "sortable": True},
                getRowId="params.data.id",
                rowClassRules={
                    "text-danger fw-semibold": "params.data.type == 'error'"
                },
                style={"height": "75vh"},
            ),
        ]
    )


@callback(
    Output("error-store", "data"),
    Input("interval-short", "n_intervals"),
    State("error-store", "data"),
)
def refresh_errors(n_intervals, current):
    """
    Copies the log received over MQTT to the browser, only when a new entry has arrived.
    """
    data = lb.snapshot()
    if current and data["counter"] == current["counter"]:
        raise PreventUpdate
    return data


@callback(
    Output("error-log", "rowData"),
    Input("error-store", "data"),
    State("timezone-store", "data"),
)
def update_error_log(data, timezone):
    if not data:
        return []
    return [
        {
            "id": str(entry["id"]),
            "time": tm.format_time(entry["received"], timezone),
            "type": entry["type"],
            "source": entry["source"],
            "code": entry["code"],
            "message": entry["message"],
        }
        for entry in data["entries"]
    ]


@callback(
    Output("error-seen-store", "data"),
    Input("url", "pathname"),
    Input("error-store", "data"),
    State("error-seen-store", "data"),
)
def mark_errors_seen(pathname, data, seen):
    """
    Marks all errors as seen while the log page is open.
    """
    if pathname != LOG_PATH or not data or data["errors"] == seen:
        raise PreventUpdate
    return data["errors"]


@callback(
    Output("log-nav-link", "children"),
    Output("log-nav-link", "style"),
    Input("error-store", "data"),
    Input("error-seen-store", "data"),
)
def update_log_tab(data, seen):
    """
    Highlights the log tab with the number of errors not yet seen in the log page.
    """
    errors = data["errors"] if data else 0
    seen = seen or 0
    # The UI restarted since the errors were last seen, so its counter started again
    if seen > errors:
        seen = 0
    unseen = errors - seen
    if unseen <= 0:
        return "Log", {}
    return f"Log ({unseen} new error{'s' if unseen > 1 else ''})", UNSEEN_STYLE
