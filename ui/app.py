from dash import Dash, html, dcc, Input, Output, callback, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from dash import Dash, html

from utils.mqtt_clients import MQTTPublisher
from config_loader import UiConfig
import os
import random
import logging

app = Dash(
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True,
)

# Import UI modules after creating the app so their global callbacks are registered.
import top_matter as tm
import main_window as mw
import control_window as cw
import instrument_setup as ss
import graph_view as gv
import experiment_config as ec
import workflow_ui as wf
import meta_data_ui as md
import saved_selector as sel
import saved_configs as sc

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

config = UiConfig()
PARAMS = config.params
PARAM_DICT = config.param_dicts
INI_EXPERIMENT_CONFIG = config.ini_experiment_config
INI_DATA_DICT = config.ini_data_dict
INI_INSTRUMENT_DICT = config.ini_instrument_dict
DEFAULTS = {
    "experiment": INI_DATA_DICT,
    "instruments": INI_INSTRUMENT_DICT,
    "config": INI_EXPERIMENT_CONFIG,
}
sel.register_selector_callbacks(DEFAULTS)


# ---------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------


def get_main_window(row_data):
    designer_layout = mw.get_experiment_designer(data=row_data, params=PARAMS)
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


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    *[State(sel.STORES[kind], "data") for kind in sc.KINDS],
    *[State(sel.meta_store_id(kind), "data") for kind in sc.KINDS],
)
def render_page(pathname, *states):
    data = dict(zip(sc.KINDS, states[: len(sc.KINDS)]))
    metas = dict(zip(sc.KINDS, states[len(sc.KINDS) :]))

    def with_selector(kind, wrapper_id):
        # The selector sits outside the wrapper so it is not rebuilt on every edit
        return html.Div(
            [
                sel.get_selector(kind, data[kind], metas[kind]),
                dcc.Loading(html.Div(id=wrapper_id)),
            ]
        )

    if pathname in ["/", None]:
        return dcc.Location(href="/designer", id="redirect")
    elif pathname == "/instrument":
        return with_selector("instruments", "instrument-wrapper")
    elif pathname == "/designer":
        return with_selector("experiment", "designer-wrapper")
    elif pathname == "/metadata":
        return metadata_layout
    elif pathname == "/control":
        return control_window
    elif pathname == "/graph":
        return graph_layout
    elif pathname == "/experiment-config":
        return with_selector("config", "experiment-config-wrapper")
    elif pathname == "/workflow":
        return metadata_workflow
    else:
        return html.Div("404 - Page not found")


def get_saved_stores():
    """
    Stores pre-populated with the latest saved version of each kind,
    so Control Panel works without visiting each tab first.
    """
    stores = []
    for kind in sc.KINDS:
        data, meta = sc.initial_state(kind, DEFAULTS[kind])
        stores.append(dcc.Store(id=sel.STORES[kind], data=data))
        stores.append(dcc.Store(id=sel.meta_store_id(kind), data=meta))
    return stores


# A function, so the latest saved versions are loaded on every page load
def serve_layout():
    return dbc.Container(
        [
            dcc.Interval(id="interval", interval=CONTROL_INTERVAL),
            dcc.Interval(id="interval-long", interval=LONG_INTERVAL),
            dcc.Interval(id="interval-short", interval=SHORT_INTERVAL),
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="timezone-store"),
            *get_saved_stores(),
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
                        className="me-0",
                    ),
                ],
                pills=True,
                justified=True,
            ),
            html.Hr(),
            html.Div(id="page-content"),
        ],
        fluid=True,
    )


app.layout = serve_layout


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(debug=False, host="0.0.0.0")
