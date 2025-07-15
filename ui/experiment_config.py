from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc

import dash_ag_grid as dag


def get_experiment_config(data=[]):
    '''
    Creates a dash-ag-grid component for sensor setup with editing.

    Should just be a table with sensor names and tolerances.
    '''
    component_id = 'experiment-config'

    column_dicts = [
        {'headerName': 'Name', 'field': 'display_name', 'editable': True},
        {'headerName': 'Name', 'field': 'name', 'editable': True, 'hide': True},
        {'headerName': 'Value', 'field': 'value', 'editable': True}
    ]

    # Layout with add/delete buttons and state
    layout = [
        dbc.Row([
            dag.AgGrid(
                id=component_id,
                columnDefs=column_dicts,
                rowData=data,
                className="ag-theme-alpine",
                defaultColDef={"editable": True, "resizable": True},
                columnSize="responsiveSizeToFit"
                # dashGridOptions={"rowSelection": "multiple", "suppressRowClickSelection": True},
            )
        ])
    ]

    return html.Div(layout, id='experiment-config-container')


@callback(
    Output("experiment-config", "rowData"),
    Input("experiment-config-store", "data")
)
def update_table(data):
    return data


@callback(
    Output("experiment-config-store", "data"),
    Input("experiment-config", "cellValueChanged"),
    State("experiment-config", "rowData"),
    prevent_initial_call=True
)
def sync_edits_to_store(cell_change, current_rows):
    return current_rows
