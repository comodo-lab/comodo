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
)
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import uuid

import dash_ag_grid as dag

import pandas as pd
import plotly.graph_objects as go

from plot import plot_data_plotly

PROFILES = ["linear", "logarithmic", "exponential", "step"]


def get_experiment_designer(data=[], params=[]):
    """
    Creates a dash-ag-grid component for experimental control data with
    editing, dropdowns, and row add/delete support.
    """
    component_id = "experiment-designer"

    # Build column list
    columns = ["time"]
    for col in params:
        columns.append(col)
        columns.append(f"{col}_profile")

    # Construct column definitions
    column_dicts = [
        {"headerName": " ".join(w.capitalize() for w in col.split("_")), "field": col}
        for col in columns
    ]

    for col in column_dicts:
        if col["field"] == "time":
            col.update({"headerName": "Time (s)", "checkboxSelection": True})
        if col["field"].endswith("_profile"):
            col.update(
                {
                    "headerName": "Profile",
                    "cellEditor": "agSelectCellEditor",
                    "cellEditorParams": {"values": PROFILES},
                }
            )

    # Prepend ID field (hidden)
    column_dicts.insert(0, {"field": "id", "hide": True})

    # Layout with add/delete buttons and state
    layout = [
        dbc.Row(
            [
                dag.AgGrid(
                    id=component_id,
                    columnDefs=column_dicts,
                    rowData=data,
                    className="ag-theme-alpine",
                    defaultColDef={"editable": True, "resizable": True},
                    columnSize="responsiveSizeToFit",
                    dashGridOptions={
                        "rowSelection": "multiple",
                        "suppressRowClickSelection": True,
                    },
                )
            ]
        ),
        html.Hr(),
        html.Div(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Button(
                                    "Add Row",
                                    id=f"{component_id}-add",
                                    n_clicks=0,
                                    color="success",
                                    className="me-1",
                                ),
                            ],
                            className="d-grid gap-2",
                        ),
                        dbc.Col(
                            [
                                dbc.Button(
                                    "Delete Selected",
                                    id=f"{component_id}-delete",
                                    n_clicks=0,
                                    color="danger",
                                    className="me-1",
                                ),
                            ],
                            className="d-grid gap-2",
                        ),
                    ]
                )
            ]
        ),
    ]

    return html.Div(layout, id="experiment-designer-container")


def get_experiment_graph(data=None):
    """
    Creates a graph to display the experimental data.
    The figure is built here rather than in a callback, as the designer is re-rendered
    on every change to experiment-designer-store.
    """
    # Copies, as plot_data_plotly removes the row ids the grid needs
    if data:
        figure = plot_data_plotly([dict(row) for row in data], xlabel="Time (s)")
    else:
        figure = go.Figure()
    graph = dcc.Graph(id="experiment-plot", figure=figure, responsive=True)
    return graph


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Input("experiment-designer-add", "n_clicks"),
    State("experiment-designer-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def add_row(n_clicks, data):
    # Fires when the designer is rendered, as prevent_initial_call does not apply
    # to inputs inserted by another callback (update_designer_page)
    if not n_clicks:
        raise PreventUpdate
    if not data:
        return data
    previous_row = data[-1]
    new_row = {key: value for key, value in previous_row.items() if key != "id"}
    new_row["id"] = str(uuid.uuid4())

    #  Add new row with time as max time +30s (default could be changed via user preferences?)
    last_time = max(
        row.get("time", 0) for row in data if isinstance(row.get("time"), (int, float))
    )
    new_row["time"] = last_time + 30
    return data + [new_row]


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Input("experiment-designer-delete", "n_clicks"),
    State("experiment-designer", "selectedRows"),
    State("experiment-designer-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def delete_selected(n_clicks, selected_rows, current_data):
    if not n_clicks:
        raise PreventUpdate
    if not selected_rows:
        return current_data
    selected_ids = {row["id"] for row in selected_rows}
    return [row for row in current_data if row["id"] not in selected_ids]


@callback(
    Output("experiment-designer-store", "data"),
    Input("experiment-designer", "cellValueChanged"),
    State("experiment-designer", "rowData"),
)
def update_table(cell_change, current_rows):
    if not cell_change:
        raise PreventUpdate
    # Sort the rows by time for presentation and ease of plotting
    sorted_rows = sorted(current_rows, key=lambda r: r.get("time", 0))
    return sorted_rows
