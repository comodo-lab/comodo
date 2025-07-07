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

CONTROL_INTERVAL = 5000  # milliseconds
SHORT_INTERVAL = 1000  # milliseconds
LONG_INTERVAL = 5000  # milliseconds

SIDE_BY_SIDE = True

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]

PARAM_DICT = [
    {'name': 'temp_left', 'min': 0, 'max': 1000, 'step': 1},
    {'name': 'temp_main', 'min': 0, 'max': 1000, 'step': 1},
    {'name': 'temp_right', 'min': 0, 'max': 1000, 'step': 1}
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

control_window = cw.get_control_window(PARAM_DICT)


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

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page(pathname):
    if pathname in ["/", None]:
        return dcc.Location(href="/designer", id="redirect")
    elif pathname == "/designer":
        return main_window
    elif pathname == "/metadata":
        return "hello"
    elif pathname == "/control":
        return "world"
    else:
        return html.Div("404 - Page not found")

app.layout = dbc.Container([
    dcc.Interval(id="interval", interval=CONTROL_INTERVAL),
    dcc.Interval(id="interval-long", interval=LONG_INTERVAL),
    dcc.Interval(id="interval-short", interval=SHORT_INTERVAL),
    dcc.Location(id="url", refresh=False),
    tm.get_header_bar(),
    dbc.Nav([
        dbc.NavItem(dbc.NavLink("Experiment Designer", href="/designer", active="exact")),
        dbc.NavItem(dbc.NavLink("Metadata Entry", href="/metadata", active="exact")),
        dbc.NavItem(dbc.NavLink("Control Panel", href="/control", active="exact")),
    ],
        pills=True,
        fill=True,
        justified=True,
    ),
    html.Hr(),
    html.Div(id="page-content")
],
fluid=True               
)


if __name__ == "__main__":
    app.run(debug=True,
            host='0.0.0.0'
            )
