from dash import Dash, html, dcc, Input, Output, callback, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from dash import Dash, html

import top_matter as tm
import main_window as mw
import control_window as cw
import instrument_setup as ss
import graph_view as gv
import experiment_config as ec
import workflow_ui as wf
import meta_data_ui as md

from utils.mqtt_clients import MQTTPublisher
import os
import random

app = Dash(
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True,
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
    Output("timezone-store", "data"),
    Input("timezone-store", "modified_timestamp"),
)

CONTROL_INTERVAL = 5000  # milliseconds
SHORT_INTERVAL = 1000  # milliseconds
LONG_INTERVAL = 5000  # milliseconds

# Params to read / actuate
PARAMS = [
    # "furnace/temperature",
    "pressure_downstream/pressure",
    "pressure_upstream/pressure",
    "massflow/massflow"
]

PARAM_DICT = [
    # {"name": "furnace/temperature", "min": 0, "max": 1000, "step": 1},
    {"name": "pressure_downstream/pressure", "min": 0, "max": 1000, "step": 1},
    {"name": "ressure_upstream/pressure", "min": 0, "max": 1000, "step": 1},
    {"name": "massflow/massflow", "min": 0, "max": 100, "step": 1},
]

INI_EXPERIMENT_CONFIG = [
    {"name": "resolution", "display_name": "Simulation Resolution (s)", "value": 1},
]


INI_DATA_DICT = [
    {
        "time": 0,
        # "furnace/temperature": 20.0,
        # "furnace/temperature_profile": "linear",
        "pressure_downstream/pressure": 20.0,
        "pressure_downstream/pressure_profile": "linear",
        "pressure_upstream/pressure": 20.0,
        "pressure_upstream/pressure_profile": "linear",
        "massflow/massflow": 20.0,
        "massflow/massflow_profile": "linear",
    },
    {
        "time": 30,
        # "furnace/temperature": 200.0,
        # "furnace/temperature_profile": "linear",
        "pressure_downstream/pressure": 40.0,
        "pressure_downstream/pressure_profile": "linear",
        "pressure_upstream/pressure": 30.0,
        "pressure_upstream/pressure_profile": "linear",
        "massflow/massflow": 25.0,
        "massflow/massflow_profile": "linear",
    },
    {
        "time": 60,
        # "furnace/temperature": 20.0,
        # "furnace/temperature_profile": "linear",
        "pressure_downstream/pressure": 30.0,
        "pressure_downstream/pressure_profile": "linear",
        "pressure_upstream/pressure": 20.0,
        "pressure_upstream/pressure_profile": "linear",
        "massflow/massflow": 20.0,
        "massflow/massflow_profile": "linear",

    }
]

INI_INSTRUMENT_DICT = [
    {
        "name": instrument,
        "tolerance": 1.0,  # Default tolerance, can be edited
    }
    for instrument in PARAMS
]


# ---------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------


def get_main_window(row_data):
    designer_layout = mw.get_experiment_designer(data=row_data)
    graph_layout = mw.get_experiment_graph()

    return html.Div([designer_layout, graph_layout])


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
    prevent_initial_call=True,
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/designer" and not current_data:
        return INI_DATA_DICT
    return no_update


# ---------------------------------------------------
# INSTRUMENT SETUP
# ---------------------------------------------------


def get_instrument_window(row_data):
    instrument_layout = ss.get_instrument_setup(data=row_data)
    return instrument_layout


@app.callback(
    Output("instrument-wrapper", "children"),
    Input("instrument-store", "data"),
)
def update_instrument_page(data):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return get_instrument_window(row_data=data)


@app.callback(
    Output("instrument-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("instrument-store", "data"),
    prevent_initial_call=True,
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/instrument" and not current_data:
        return INI_INSTRUMENT_DICT
    return no_update


# ---------------------------------------------------
# EXPERIMENT CONFIG
# ---------------------------------------------------


def get_experiment_config_window(row_data):
    instrument_layout = ec.get_experiment_config(data=row_data)
    return instrument_layout


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
    prevent_initial_call=True,
)
def initialize_experiment_store(pathname, current_data):
    if pathname == "/experiment-config" and not current_data:
        return INI_EXPERIMENT_CONFIG
    return no_update


control_window = cw.get_control_panel(PARAM_DICT)
graph_layout = gv.get_experiment_graph()
metadata_workflow = wf.get_workflow_layout()

metadata_layout = md.get_metadata_layout()
# Register metadata callbacks 
wf.register_workflow_callbacks(app)

@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname):
    if pathname in ["/", None]:
        return dcc.Location(href="/designer", id="redirect")
    elif pathname == "/instrument":
        return dcc.Loading(html.Div(id="instrument-wrapper"))
    elif pathname == "/designer":
        return dcc.Loading(html.Div(id="designer-wrapper"))
    elif pathname == "/metadata":
        return metadata_layout
    elif pathname == "/control":
        return control_window
    elif pathname == "/graph":
        return graph_layout
    elif pathname == "/experiment-config":
        return dcc.Loading(html.Div(id="experiment-config-wrapper"))
    elif pathname == "/workflow":
        return metadata_workflow
    else:
        return html.Div("404 - Page not found")


app.layout = dbc.Container(
    [
        dcc.Interval(id="interval", interval=CONTROL_INTERVAL),
        dcc.Interval(id="interval-long", interval=LONG_INTERVAL),
        dcc.Interval(id="interval-short", interval=SHORT_INTERVAL),
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="timezone-store"),
        dcc.Store(id="experiment-designer-store"),
        dcc.Store(id="instrument-store"),
        dcc.Store(id="experiment-config-store"),
        html.Div(id="hidden-div", style={"display": "none"}),
        tm.get_header_bar(),
        dbc.Nav(
            [
                dbc.NavItem(
                    dbc.NavLink(
                        "Experiment Designer", href="/designer", active="exact"
                    ),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink("Instrument Setup", href="/instrument", active="exact"),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink(
                        "Experiment Config", href="/experiment-config", active="exact"
                    ),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink("Metadata Entry", href="/metadata", active="exact"),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink("Control Panel", href="/control", active="exact"),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink("Graph View", href="/graph", active="exact"),
                    className="me-0",
                ),
                dbc.NavItem(
                    dbc.NavLink("Workflow", href="/workflow", active="exact"), 
                    className="me-0"),
            ],
            pills=True,
            justified=True,
        ),
        html.Hr(),
        html.Div(id="page-content"),
    ],
    fluid=True,
)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
