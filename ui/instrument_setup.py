import json

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

import dash_ag_grid as dag


def parse_value(value):
    """
    Returns the value of a row as typed in the table: numbers, booleans, lists and
    objects are read as JSON, anything else is kept as text.
    """
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


def to_instrument_config(rows):
    """
    Groups instrument live config rows ({name, key, value}) per instrument, as expected
    by the controller. Rows for a variable (instrument/variable) are nested under it:
        furnace              offset     273  ->  {"furnace": {"offset": 273,
        furnace/temperature  tolerance  1                     "temperature": {"tolerance": 1}}}
    Rows without a name or key are ignored.
    """
    config = {}
    for row in rows or []:
        name = str(row.get("name") or "").strip()
        key = str(row.get("key") or "").strip()
        if not name or not key:
            continue
        instrument, _, variable = name.partition("/")
        target = config.setdefault(instrument, {})
        if variable:
            target = target.setdefault(variable, {})
            if not isinstance(target, dict):
                raise ValueError(
                    f"Instrument '{instrument}' has both a '{variable}' key and variable."
                )
        target[key] = parse_value(row.get("value"))
    return config


def get_instrument_setup(data=[]):
    """
    Creates a dash-ag-grid component for the instrument live config, with editing and
    row add/delete support. Each row sets a key of an instrument (instrument) or of one
    of its variables (instrument/variable).
    """
    component_id = "instrument_setup"

    column_dicts = [
        {
            "headerName": "Instrument / Variable",
            "field": "name",
            "checkboxSelection": True,
        },
        {"headerName": "Parameter", "field": "key"},
        # Edited as text, so values of any type can be entered (read by parse_value)
        {"headerName": "Value", "field": "value", "cellDataType": False},
    ]

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
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Add Row",
                        id=f"{component_id}-add",
                        n_clicks=0,
                        color="success",
                        className="me-1",
                    ),
                    className="d-grid gap-2",
                ),
                dbc.Col(
                    dbc.Button(
                        "Delete Selected",
                        id=f"{component_id}-delete",
                        n_clicks=0,
                        color="danger",
                        className="me-1",
                    ),
                    className="d-grid gap-2",
                ),
            ]
        ),
    ]

    return html.Div(layout, id="instrument-setup-container")


@callback(Output("instrument_setup", "rowData"), Input("instrument-store", "data"))
def update_table(data):
    return data


@callback(
    Output("instrument-store", "data"),
    Input("instrument_setup", "cellValueChanged"),
    State("instrument_setup", "rowData"),
    prevent_initial_call=True,
)
def sync_edits_to_store(cell_change, current_rows):
    if not cell_change:
        raise PreventUpdate
    return current_rows


@callback(
    Output("instrument-store", "data", allow_duplicate=True),
    Input("instrument_setup-add", "n_clicks"),
    State("instrument-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def add_row(n_clicks, data):
    # Fires when the table is rendered, as prevent_initial_call does not apply
    # to inputs inserted by another callback (update_instrument_page)
    if not n_clicks:
        raise PreventUpdate
    return (data or []) + [{"name": "", "key": "", "value": ""}]


@callback(
    Output("instrument-store", "data", allow_duplicate=True),
    Input("instrument_setup-delete", "n_clicks"),
    State("instrument_setup", "selectedRows"),
    State("instrument-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def delete_selected(n_clicks, selected_rows, current_data):
    if not n_clicks:
        raise PreventUpdate
    if not selected_rows:
        return current_data
    return [row for row in current_data if row not in selected_rows]
