import os
import random
import logging

from dash import Dash, html, dcc, Input, Output, callback, State, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from utils.mqtt_clients import MQTTPublisher

from src.config_loader import UiConfig

app = Dash(
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True,
)

# Import UI modules after creating the app so their global callbacks are registered.
from src import (
    control_window as cw,
    experiment_config as ec,
    graph_view as gv,
    heartbeats as hb,
    instrument_setup as ins,
    log_book as lb,
    log_window as lw,
    main_window as mw,
    saved_configs as sc,
    saved_selector as sel,
    spc_setup as spc,
    top_matter as tm,
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

config = UiConfig()
PARAMS = config.params
PARAM_DICT = config.param_dicts
INI_EXPERIMENT_CONFIG = config.ini_experiment_config
INI_DATA_DICT = config.ini_data_dict
INI_INSTRUMENT_DICT = config.ini_instrument_dict
INI_SPC_DICT = config.ini_spc_dict
DEFAULTS = {
    "experiment": INI_DATA_DICT,
    "instruments": INI_INSTRUMENT_DICT,
    "config": INI_EXPERIMENT_CONFIG,
    "spcs": INI_SPC_DICT,
}
sel.register_selector_callbacks(DEFAULTS)

# Listen to controller, instrument and SPC heartbeats
hb.start(
    config.config,
    id=f"ui-heartbeats-{id_suffix}",
    broker_address=os.getenv("MQTT_HOST"),
    user=os.getenv("MQTT_USER"),
    password=os.getenv("MQTT_PASS"),
    connection_timeout=5,
)

# Listen to errors published by any component and experiment lifecycle messages
lb.start(
    id=f"ui-errors-{id_suffix}",
    broker_address=os.getenv("MQTT_HOST"),
    user=os.getenv("MQTT_USER"),
    password=os.getenv("MQTT_PASS"),
    connection_timeout=5,
)


# ---------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------


def get_main_window(row_data, resolution=1):
    designer_layout = mw.get_experiment_designer(data=row_data, params=PARAMS)
    graph_layout = mw.get_experiment_graph(data=row_data, resolution=resolution)

    return html.Div([designer_layout, graph_layout])


@app.callback(
    Output("designer-wrapper", "children"),
    Input("experiment-designer-store", "data"),
    Input("experiment-config-store", "data"),
)
def update_designer_page(data, exp_config):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return get_main_window(row_data=data, resolution=ec.get_resolution(exp_config))


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
    instrument_layout = ins.get_instrument_setup(data=row_data)
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
# PID SETUP
# ---------------------------------------------------


@app.callback(
    Output("spc-wrapper", "children"),
    Input("spc-store", "data"),
)
def update_spc_page(data):
    if data is None:
        raise PreventUpdate  # Wait for initialization
    return spc.get_spc_setup(data=data)


@app.callback(
    Output("spc-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    State("spc-store", "data"),
    prevent_initial_call=True,
)
def initialize_spc_store(pathname, current_data):
    if pathname == "/pid" and not current_data:
        return INI_SPC_DICT
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
log_window = lw.get_log_window()


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
    elif pathname == "/pid":
        return with_selector("spcs", "spc-wrapper")
    elif pathname == "/designer":
        return with_selector("experiment", "designer-wrapper")
    elif pathname == "/control":
        return control_window
    elif pathname == "/graph":
        return graph_layout
    elif pathname == "/experiment-config":
        return with_selector("config", "experiment-config-wrapper")
    elif pathname == lw.LOG_PATH:
        return log_window
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
            dcc.Store(id="heartbeat-store"),
            dcc.Store(id="error-store"),
            # Kept per browser tab, so reloading does not show seen errors as new
            dcc.Store(id="error-seen-store", storage_type="session"),
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
                        dbc.NavLink(
                            "Instrument Setup",
                            href="/instrument",
                            active="exact",
                        ),
                        className="me-0",
                    ),
                    dbc.NavItem(
                        dbc.NavLink("PID Setup", href="/pid", active="exact"),
                        className="me-0",
                    ),
                    dbc.NavItem(
                        dbc.NavLink(
                            "Experiment Config",
                            href="/experiment-config",
                            active="exact",
                        ),
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
                        dbc.NavLink(
                            "Log", href=lw.LOG_PATH, active="exact", id="log-nav-link"
                        ),
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
