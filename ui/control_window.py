from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import uuid

import dash_ag_grid as dag

import pandas as pd
import plotly.graph_objects as go

from plot import plot_data_plotly


def get_control_window():
    """
    Creates the control window for the experiment designer.
    """
    component_id = 'control-window'

    # Define the layout of the control window
    control_window = dbc.Container([
        dbc.Row(html.H2("Control Window")),
        dbc.Row(
            dbc.Col(
                dag.AgGrid(
                    id=component_id,
                    columnDefs=[
                        {'headerName': 'Parameter', 'field': 'parameter'},
                        {'headerName': 'Value', 'field': 'value'},
                        {'headerName': 'Action', 'field': 'action'}
                    ],
                    rowData=[],
                    defaultColDef={'editable': True, 'sortable': True, 'filter': True},
                ),
                width=12
            )
        ),
        dbc.Row(
            html.H4("HOLDING TEXT"),
        ),
    ], fluid=True)

    return control_window