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


def get_instrument_setup(data=[]):
    """
    Creates a dash-ag-grid component for instrument setup with editing.

    Should just be a table with instrument names and tolerances.
    """
    component_id = "instrument_setup"

    column_dicts = [
        {"headerName": "Instrument Name", "field": "name", "editable": True},
        {"headerName": "Tolerance", "field": "tolerance", "editable": True},
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
                    # dashGridOptions={"rowSelection": "multiple", "suppressRowClickSelection": True},
                )
            ]
        )
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
