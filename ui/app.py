from dash import Dash, html, dcc, Input, Output, callback, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from dash import Dash, html

import top_matter as tm
import main_window as mw
import control_window as cw
import sensor_setup as ss
import graph_view as gv
import experiment_config as ec

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
    broker_address=os.getenv("MQTT_HOST"),
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

PARAMS = [
    "temp_left",
    "temp_main",
    "temp_right",
    "pressure_downstream",
    "pressure_upstream",
    "massflow",
    "massflow_temp",
    "massflow_pressure_upstream",
    "massflow_pressure_downstream",
    "massflow_fluid_temp",
    "mass_spec",
]

PARAM_DICT = [
    {'name': 'temp_left', 'min': 0, 'max': 1000, 'step': 1},
    {'name': 'temp_main', 'min': 0, 'max': 1000, 'step': 1},
    {'name': 'temp_right', 'min': 0, 'max': 1000, 'step': 1},
    # {'name': 'massflow', 'min': 0, 'max': 100, 'step': 0.1},
]

INI_EXPERIMENT_CONFIG = [
    {'name': 'resolution', 'display_name': 'Simulation Resolution (s)', 'value': 1},
]


INI_DATA_DICT = [
    {'time': 0, 'temp_left': 0.0, 'temp_left_profile': 'linear', 'temp_main': 0.0, 'temp_main_profile': 'linear', 'temp_right': 0.0, 'temp_right_profile': 'linear'}, #, 'massflow': 0.0, 'massflow_profile': 'linear'},
    {'time': 30, 'temp_left': 250.0, 'temp_left_profile': 'exponential', 'temp_main': 300.0, 'temp_main_profile': 'linear', 'temp_right': 250.0, 'temp_right_profile': 'exponential'}, #, 'massflow': 25.0, 'massflow_profile': 'exponential'},
    {'time': 60, 'temp_left': 0.0, 'temp_left_profile': 'step', 'temp_main': 0.0, 'temp_main_profile': 'step', 'temp_right': 0.0, 'temp_right_profile': 'step'}, #, 'massflow': 0.0, 'massflow_profile': 'step'}
]


INI_SENSOR_DICT = [{
    'name': sensor,
    'p': 0.21,
    'i': 0.31,
    'd': 0.41,
    'tolerance': 1.0  # Default tolerance, can be edited
} for sensor in PARAMS]



# ---------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------

def get_main_window(row_data):
    designer_layout = mw.get_experiment_designer(params=PARAMS, data=row_data)
    graph_layout = mw.get_experiment_graph()

    return dbc.Row([
        dbc.Col(designer_layout),
        dbc.Col(graph_layout)
    ])


@app.callback(
    Output("designer-wrapper", "children"),
    Input("experiment-designer-store", "data"),
)
def update_designer_page(data):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return get_main_window(row_data=data)


@app.callback(
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("experiment-designer-store", "data"),
    prevent_initial_call=True
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/designer" and not current_data:
        return INI_DATA_DICT
    return no_update


# ---------------------------------------------------
# SENSOR SETUP
# ---------------------------------------------------

def get_sensor_window(row_data):
    sensor_layout = ss.get_sensor_setup(data=row_data)
    return sensor_layout


@app.callback(
    Output("sensor-wrapper", "children"),
    Input("sensor-store", "data"),
)
def update_sensor_page(data):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return get_sensor_window(row_data=data)


@app.callback(
    Output("sensor-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("sensor-store", "data"),
    prevent_initial_call=True
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/sensor" and not current_data:
        return INI_SENSOR_DICT
    return no_update


# ---------------------------------------------------
# EXPERIMENT CONFIG
# ---------------------------------------------------

def get_experiment_config_window(row_data):
    sensor_layout = ec.get_experiment_config(data=row_data)
    return sensor_layout


@app.callback(
    Output("experiment-config-wrapper", "children"),
    Input("experiment-config-store", "data"),
)
def update_experiment_config_page(data):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return get_experiment_config_window(row_data=data)


@app.callback(
    Output("experiment-config-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("experiment-config-store", "data"),
    prevent_initial_call=True
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/experiment-config" and not current_data:
        return INI_EXPERIMENT_CONFIG
    return no_update


control_window = cw.get_control_panel(PARAM_DICT)
graph_layout = gv.get_experiment_graph()



@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def render_page(pathname):
    if pathname in ["/", None]:
        return dcc.Location(href="/designer", id="redirect")
    elif pathname == "/sensor":
        return dcc.Loading(html.Div(id='sensor-wrapper'))
    elif pathname == "/designer":
        return dcc.Loading(html.Div(id='designer-wrapper'))
    elif pathname == "/metadata":
        return "hello"
    elif pathname == "/control":
        return control_window
    elif pathname == "/graph":
        return graph_layout
    elif pathname == "/experiment-config":
        return dcc.Loading(html.Div(id='experiment-config-wrapper'))
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
    dcc.Store(id='experiment-config-store'),
    html.Div(id='hidden-div', style={'display': 'none'}),
    tm.get_header_bar(),
    dbc.Nav([
        dbc.NavItem(dbc.NavLink("Experiment Designer", href="/designer", active="exact"), className="me-0"),
        dbc.NavItem(dbc.NavLink("Sensor Setup", href="/sensor", active="exact"), className="me-0"),
        dbc.NavItem(dbc.NavLink("Experiment Config", href="/experiment-config", active="exact"), className="me-0"),
        dbc.NavItem(dbc.NavLink("Metadata Entry", href="/metadata", active="exact"), className="me-0"),
        dbc.NavItem(dbc.NavLink("Control Panel", href="/control", active="exact"), className="me-0"),
        dbc.NavItem(dbc.NavLink("Graph View", href="/graph", active="exact"), className="me-0"),
    ],
        pills=True,
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
