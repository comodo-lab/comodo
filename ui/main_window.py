from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc

import pandas as pd
import plotly.graph_objects as go


PROFILES = [
    'linear',
    'logarithmic',
    'exponential',
    'step'
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
    Creates a table to display the experimental control data.
    '''
    id = 'experiment-designer'
    columns = ['time']
    for col in params:
        columns.append(col)
        columns.append(f'{col}_profile')
    if initial_data is None:
        data = ini_data_dict
        # data = [dict(time=i, **{param: 0 for param in columns if param != 'time'}) for i in range(1, 5)]
    else:
        data = initial_data

    profile_options = {
        'options': [
            {'label': profile.capitalize(), 'value': profile}
            for profile in PROFILES
        ]
    }
    dropdowns = dict(**{col: profile_options for col in columns if col.endswith('_profile')})

    print(f"Creating table with columns: {columns} and data: {data}")
    print(f"Dropdowns: {dropdowns}")

    column_dict = [{'name': ' '.join(word.capitalize() for word in col.split('_')), 'id': col} for col in columns]

    for idx, col in enumerate(column_dict):
        if col['id'].endswith('_profile'):
            column_dict[idx]['presentation'] = 'dropdown'

    print(f"Column dict: {column_dict}")

    css_dropdown = [{"selector":".dropdown", "rule": "position: static"}]

    table = dash_table.DataTable(
        id=id,
        columns=column_dict,
        data=data,
        editable=True,
        row_deletable=True,
        dropdown=dropdowns,
        css=css_dropdown,
    )
    return table


@callback(
    Output('experiment-designer', 'data'),
    Input('editing-rows-button', 'n_clicks'),
    State('experiment-designer', 'data'),
    State('experiment-designer', 'columns'))
def add_row(n_clicks, rows, columns):
    if n_clicks > 0:
        rows.append({c['id']: '' for c in columns})
    return rows


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
