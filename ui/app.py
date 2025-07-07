from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px

import dash_ag_grid as dag
from dash import Dash, html

import top_matter as tm
import main_window as mw

app = Dash(
    external_stylesheets=[dbc.themes.LUX]
)

SIDE_BY_SIDE = True

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]

if SIDE_BY_SIDE:
    main_window = dbc.Row([
                dbc.Col(
                    mw.get_experiment_designer(params=PARAMS, initial_data=None)
                ),
                dbc.Col(
                    mw.get_experiment_graph()
                )
            ])
else:
    main_window = dbc.Row(
                dbc.Col(
                    mw.get_experiment_designer(params=PARAMS, initial_data=None),
                    width=12
                )
            ),
    main_window += dbc.Row(
                dbc.Col(
                    mw.get_experiment_graph(),
                    width=12
                )
            )

app.layout = dbc.Container([
        tm.get_header_bar(),
        main_window,
])


if __name__ == "__main__":
    app.run(debug=True,
            host='0.0.0.0'
            )
