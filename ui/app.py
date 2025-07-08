from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px

import dash_ag_grid as dag
from dash import Dash, html

import top_matter as tm
import main_window as mw
import control_window as cw
import sensor_setup as ss

from utils.mqtt_clients import MQTTPublisher
import os
import random

app = Dash(
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True
)

# Initialise publisher singleton
id_suffix = random.randint(0, 32768)
publisher = MQTTPublisher.get_instance(
    id=f"ui-publisher-{id_suffix}",
    broker_address=os.getenv("MQTT_ADDR"),
    user=os.getenv("MQTT_USER"),
    password=os.getenv("MQTT_PASS"),
    connection_timeout=5,
)


app.clientside_callback(
    """
    function(n_clicks) {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    }
    """,
    Output('timezone-store', 'data'),
    Input('timezone-store', 'modified_timestamp')
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

# @callback(
#     Output("tab-content", "children"),
#     Input("tab-selector", "value")
# )
# def render_tab_content(tab):
#     if tab == "control":
#         return control_window
#     elif tab == "main":
#         return main_window
#     else:
#         return html.Div("No content available for this tab.")

@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page(pathname):
    if pathname in ["/", None]:
        return dcc.Location(href="/designer", id="redirect")
    elif pathname == "/sensor":
        return ss.get_sensor_setup(params=PARAMS)
    elif pathname == "/designer":
        return main_window
    elif pathname == "/metadata":
        return "hello"
    elif pathname == "/control":
        return cw.get_control_panel()
    else:
        return html.Div("404 - Page not found")


app.layout = dbc.Container([
    dcc.Interval(id="interval", interval=CONTROL_INTERVAL),
    dcc.Interval(id="interval-long", interval=LONG_INTERVAL),
    dcc.Interval(id="interval-short", interval=SHORT_INTERVAL),
    dcc.Location(id="url", refresh=False),
    dcc.Store(id='timezone-store'),
    dcc.Store(id='experiment-designer-store'),
    dcc.Store(id='sensor-store'),
    html.Div(id='hidden-div', style={'display': 'none'}),
    tm.get_header_bar(),
    dbc.Nav([
        dbc.NavItem(dbc.NavLink("Experiment Designer", href="/designer", active="exact")),
        dbc.NavItem(dbc.NavLink("Sensor Setup", href="/sensor", active="exact")),
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
