from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px

import dash_ag_grid as dag
from dash import Dash, html

import top_matter as tm
import main_window as mw
import control_window as cw

app = Dash(
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True
)

SIDE_BY_SIDE = True

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]

designer_layout = mw.get_experiment_designer(params=PARAMS, initial_data=None)
graph_layout = mw.get_experiment_graph()

if SIDE_BY_SIDE:
    main_window = dbc.Row([
        dbc.Col(designer_layout),
        dbc.Col(graph_layout)
    ])
else:
    main_window = html.Div([
        dbc.Row(dbc.Col(designer_layout, width=12)),
        dbc.Row(dbc.Col(graph_layout, width=12))
    ])

control_window = cw.get_control_window()


@callback(
    Output("tab-content", "children"),
    Input("tab-selector", "value")
)
def render_tab_content(tab):
    if tab == "control":
        return control_window
    elif tab == "main":
        return main_window
    else:
        return html.Div("No content available for this tab.")


app.layout = html.Div(
    [
        dcc.Interval(id="interval", interval=1000),
        dcc.Interval(id="interval-long", interval=5000),
        tm.get_header_bar(0),
        dcc.Tabs(
            children=[
                dcc.Tab(label="Main", value="main"),
                dcc.Tab(label="Control", value="control"),
            ],
            id="tab-selector",
            value="main",
        ),
        html.Div(id="tab-content"),
    ]
)


if __name__ == "__main__":
    app.run(debug=True,
            host='0.0.0.0'
            )
