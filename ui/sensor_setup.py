from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc

import dash_ag_grid as dag


def get_sensor_setup(params=[]):
    '''
    Creates a dash-ag-grid component for sensor setup with editing.

    Should just be a table with sensor names and tolerances.
    '''
    component_id = 'sensor_setup'

    column_dicts = [{'headerName': 'Sensor Name', 'field': 'name', 'editable': True},
                    {'headerName': 'P', 'field': 'p', 'editable': True},
                    {'headerName': 'I', 'field': 'i', 'editable': True},
                    {'headerName': 'D', 'field': 'd', 'editable': True},
                    {'headerName': 'Tolerance', 'field': 'tolerance', 'editable': True},
                    {'headerName': 'Resolution', 'field': 'resolution', 'editable': True}
                    ]

    data = []
    for param in params:
        data.append({
            'name': param,
            'p': 0.21,
            'i': 0.31,
            'd': 0.41,
            'tolerance': 1.0,  # Default tolerance, can be edited
            'resolution': 1.0
        })

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

    return html.Div(layout, id='sensor-setup-container')


@callback(
    Output("sensor_setup", "rowData"),
    Input("sensor-store", "data")
)
def update_table(data):
    return data


@callback(
    Output("sensor-store", "data", allow_duplicate=True),
    Input("sensor_setup", "cellValueChanged"),
    State("sensor_setup", "rowData"),
    prevent_initial_call=True
)
def sync_edits_to_store(cell_change, current_rows):
    return current_rows
