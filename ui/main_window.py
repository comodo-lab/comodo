from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import uuid

import dash_ag_grid as dag

import pandas as pd
import plotly.graph_objects as go

from plot import plot_data_plotly


PROFILES = [
    'linear',
    'logarithmic',
    'exponential',
    'step'
]

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]

ini_data_dict = [
    {'time': 0, 'temp_left': 0.0, 'temp_left_profile': 'linear', 'temp_main': 0.0, 'temp_main_profile': 'linear', 'temp_right': 0.0, 'temp_right_profile': 'linear'},
    {'time': 30, 'temp_left': 250.0, 'temp_left_profile': 'exponential', 'temp_main': 300.0, 'temp_main_profile': 'linear', 'temp_right': 250.0, 'temp_right_profile': 'exponential'},
    {'time': 60, 'temp_left': 300.0, 'temp_left_profile': 'step', 'temp_main': 350.0, 'temp_main_profile': 'step', 'temp_right': 350.0, 'temp_right_profile': 'step'},
    {'time': 90, 'temp_left': 200.0, 'temp_left_profile': 'linear', 'temp_main': 200.0, 'temp_main_profile': 'linear', 'temp_right': 200.0, 'temp_right_profile': 'linear'},
    {'time': 120, 'temp_left': 0.0, 'temp_left_profile': 'linear', 'temp_main': 0.0, 'temp_main_profile': 'linear', 'temp_right': 0.0, 'temp_right_profile': 'linear'}
]


def get_experiment_designer(params=[], initial_data=None):
    '''
    Creates a dash-ag-grid component for experimental control data with editing,
    dropdowns, and row add/delete support.
    '''
    component_id = 'experiment-designer'

    # Build column list
    columns = ['time']
    for col in params:
        columns.append(col)
        columns.append(f'{col}_profile')

    # Use provided data or fallback to sample
    if initial_data is None:
        data = ini_data_dict
    else:
        data = initial_data

    # Ensure each row has a unique ID
    for row in data:
        row.setdefault("id", str(uuid.uuid4()))

    # Construct column definitions
    column_dicts = [{'headerName': ' '.join(w.capitalize() for w in col.split('_')), 'field': col}
                    for col in columns]

    for col in column_dicts:
        if col['field'] == 'time':
            col.update({
                'headerName': 'Time (s)',
                "checkboxSelection": True
            })
        if col['field'].endswith('_profile'):
            col.update({
                'headerName': 'Profile',
                'cellEditor': 'agSelectCellEditor',
                'cellEditorParams': {'values': PROFILES}
            })

    # Prepend ID field (hidden)
    column_dicts.insert(0, {
        'field': 'id',
        'hide': True
    })

    # Layout with add/delete buttons and state
    layout = html.Div([
        html.Div([
            html.Button("Add Row", id=f"{component_id}-add", n_clicks=0, className="btn btn-success me-2"),
            html.Button("Delete Selected", id=f"{component_id}-delete", n_clicks=0, className="btn btn-danger"),
        ], className="my-2"),

        dcc.Store(id=f"{component_id}-store", data=data),

        dag.AgGrid(
            id=component_id,
            columnDefs=column_dicts,
            rowData=data,
            className="ag-theme-alpine",
            defaultColDef={"editable": True, "resizable": True},
            columnSize="responsiveSizeToFit",
            dashGridOptions={"rowSelection": "multiple", "suppressRowClickSelection": True},
        )
    ])

    return layout


def get_experiment_graph():
    """
    Creates a graph to display the experimental data.
    """
    graph = dcc.Graph(id='experiment-plot')
    # dcc.Graph(id='experiment-plot', figure=fig)

    return graph


@callback(
    Output("experiment-designer", "rowData"),
    Input("experiment-designer-store", "data")
)
def update_table(data):
    return data


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Input("experiment-designer-add", "n_clicks"),
    State("experiment-designer-store", "data"),
    prevent_initial_call="initial_duplicate"
)
def add_row(n_clicks, data):
    new_row = {"id": str(uuid.uuid4())}
    for col in data[0]:
        if col == "id":
            continue
        elif col.endswith("_profile"):
            new_row[col] = PROFILES[0]
        else:
            new_row[col] = 0.0 if col != "time" else 0
    return data + [new_row]


@callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Input("experiment-designer-delete", "n_clicks"),
    State("experiment-designer", "selectedRows"),
    State("experiment-designer-store", "data"),
    prevent_initial_call="initial_duplicate"
)
def delete_selected(n_clicks, selected_rows, current_data):
    if not selected_rows:
        return current_data
    selected_ids = {row["id"] for row in selected_rows}
    return [row for row in current_data if row["id"] not in selected_ids]


@callback(
    Output("experiment-plot", "figure"),
    Input("experiment-designer", "cellValueChanged"),
    Input("interval-long", "n_intervals"),
    State("experiment-designer-store", "data"),
)
def update(cell_changed, n_intervals, data):
    if cell_changed is None:
        return

    print("Cell changed:", data)

    # new_data = cell_changed[0]['data']
    # y = []
    # for param in PARAMS:
    #     y.append(new_data[param])
    fig = plot_data_plotly(data, title="Experiment Data Plot", xlabel="Time (s)", ylabel="Temperature")
    return fig


def get_main_window(params=[], initial_data=None):
    """
    Creates the main window of the application.
    """
    main_window = html.Div([
        get_experiment_designer(params=params, initial_data=initial_data),
        html.Button('Add Row', id='editing-rows-button', n_clicks=0),
        # dcc.Graph(id='adding-rows-graph')
    ])

    return main_window
