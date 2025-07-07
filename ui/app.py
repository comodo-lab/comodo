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
