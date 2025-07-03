from dash import Dash, html, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

# import yaml

import top_matter as tm
import main_window as mw

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]  # TODO: Would get these from config or ttl in future

app = Dash(external_stylesheets=[dbc.themes.FLATLY])


app.layout = dbc.Container(
    [
        tm.get_header_bar(),
        mw.get_main_window(params=PARAMS, initial_data=None),
    ],
    fluid=True,
    className="p-4 bg-light rounded",
)

if __name__ == '__main__':
    app.run(debug=True,
            host='0.0.0.0'
            )
