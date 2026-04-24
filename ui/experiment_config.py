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
import dash_bootstrap_components as dbc
import base64
import json

import dash_ag_grid as dag

from main_window import _parse_load, _split_load


def get_experiment_config(data=[]):
    """
    Creates a dash-ag-grid component for instrument setup with editing.

    Should just be a table with instrument names and tolerances.
    """
    component_id = "experiment-config"

    column_dicts = [
        {"headerName": "Name", "field": "display_name", "editable": True},
        {"headerName": "Name", "field": "name", "editable": True, "hide": True},
        {"headerName": "Value", "field": "value", "editable": True},
    ]

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
                    dashGridOptions={"domLayout": "autoHeight"},
                )
            ]
        ),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-download me-1"), "Save"],
                        id="experiment-save-config", n_clicks=0, color="primary",
                    ),
                    className="d-grid",
                ),
                dbc.Col(
                    dcc.Upload(
                        dbc.Button(
                            [html.I(className="bi bi-upload me-1"), "Load"],
                            color="primary", style={"width": "100%"},
                        ),
                        id="experiment-load-config",
                        accept=".json",
                        style={"width": "100%"},
                    ),
                    className="d-grid",
                ),
            ],
            className="g-2 mt-1",
        ),
    ]

    return html.Div(layout, id="experiment-config-container")


@callback(
    Output("experiment-config", "rowData"), Input("experiment-config-store", "data")
)
def update_config_table(data):
    return data


@callback(
    Output("experiment-config-store", "data"),
    Input("experiment-config", "cellValueChanged"),
    State("experiment-config", "rowData"),
    prevent_initial_call=True,
)
def sync_config_edits_to_store(cell_change, current_rows):
    return current_rows


@callback(
    Output("save-trigger", "data", allow_duplicate=True),
    Input("experiment-save-config", "n_clicks"),
    prevent_initial_call=True,
)
def trigger_save_config(n):
    if not n:
        return no_update
    return n


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Output("instrument-store", "data", allow_duplicate=True),
    Output("experiment-config-store", "data", allow_duplicate=True),
    Input("experiment-load-config", "contents"),
    prevent_initial_call=True,
)
def load_from_config(contents):
    if not contents:
        return no_update, no_update, no_update
    try:
        exp_rows, inst_rows, cfg_rows = _split_load(_parse_load(contents))
        return exp_rows, inst_rows, cfg_rows
    except Exception:
        return no_update, no_update, no_update
