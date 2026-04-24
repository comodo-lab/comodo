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


def get_instrument_setup(data=[]):
    """
    Creates a dash-ag-grid component for instrument setup with editing.

    Should just be a table with instrument names and tolerances.
    """
    component_id = "instrument_setup"

    column_dicts = [
        {"headerName": "Instrument Name", "field": "name", "editable": True},
        {"headerName": "Tolerance", "field": "tolerance", "editable": True},
        {"headerName": "Default Setpoint", "field": "default_setpoint", "editable": True},
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
                        id="experiment-save-instrument", n_clicks=0, color="primary",
                    ),
                    className="d-grid",
                ),
                dbc.Col(
                    dcc.Upload(
                        dbc.Button(
                            [html.I(className="bi bi-upload me-1"), "Load"],
                            color="primary", style={"width": "100%"},
                        ),
                        id="experiment-load-instrument",
                        accept=".json",
                        style={"width": "100%"},
                    ),
                    className="d-grid",
                ),
            ],
            className="g-2 mt-1",
        ),
    ]

    return html.Div(layout, id="instrument-setup-container")


@callback(Output("instrument_setup", "rowData"), Input("instrument-store", "data"))
def update_instrument_table(data):
    return data


@callback(
    Output("instrument-store", "data"),
    Input("instrument_setup", "cellValueChanged"),
    State("instrument_setup", "rowData"),
    prevent_initial_call=True,
)
def sync_instrument_edits_to_store(cell_change, current_rows):
    return current_rows


@callback(
    Output("save-trigger", "data", allow_duplicate=True),
    Input("experiment-save-instrument", "n_clicks"),
    prevent_initial_call=True,
)
def trigger_save_instrument(n):
    if not n:
        return no_update
    return n


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Output("instrument-store", "data", allow_duplicate=True),
    Output("experiment-config-store", "data", allow_duplicate=True),
    Input("experiment-load-instrument", "contents"),
    prevent_initial_call=True,
)
def load_from_instrument(contents):
    if not contents:
        return no_update, no_update, no_update
    try:
        exp_rows, inst_rows, cfg_rows = _split_load(_parse_load(contents))
        return exp_rows, inst_rows, cfg_rows
    except Exception:
        return no_update, no_update, no_update
