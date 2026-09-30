from dash import html, dcc, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

import saved_configs as sc

# Store holding the data of each kind of saved configuration
STORES = {
    "experiment": "experiment-designer-store",
    "instruments": "instrument-store",
    "config": "experiment-config-store",
}


def meta_store_id(kind):
    return f"{kind}-meta-store"


def get_status_badge(data, meta):
    if data is None or meta is None:
        return ""
    if sc.is_dirty(data, meta):
        return dbc.Badge("Unsaved changes", color="warning")
    return dbc.Badge("Saved", color="success")


def get_selector(kind, data, meta):
    """
    Creates a bar to load a saved version of kind, name it and save it.
    """
    return dbc.Row(
        [
            dbc.Col(
                dcc.Dropdown(
                    id=f"{kind}-saved-select",
                    options=sc.list_saved(kind),
                    value=meta["file"],
                    clearable=False,
                ),
                width=5,
            ),
            dbc.Col(
                dbc.Input(
                    id=f"{kind}-saved-name",
                    value=meta["name"],
                    placeholder="Name",
                ),
                width=4,
            ),
            dbc.Col(
                dbc.Button("Save", id=f"{kind}-saved-save", color="primary"),
                width=1,
                className="d-grid",
            ),
            dbc.Col(
                html.Div(get_status_badge(data, meta), id=f"{kind}-saved-status"),
                width=2,
            ),
        ],
        className="mb-3 align-items-center",
    )


def register_selector_callbacks(defaults):
    """
    Registers the selector callbacks for each kind.
    defaults maps each kind to its default data, used to fit loaded files to the current config.
    """
    for kind, store_id in STORES.items():
        _register_kind(kind, store_id, defaults[kind])


def _register_kind(kind, store_id, default):
    meta_id = meta_store_id(kind)

    @callback(
        Output(store_id, "data", allow_duplicate=True),
        Output(meta_id, "data", allow_duplicate=True),
        Output(f"{kind}-saved-name", "value"),
        Input(f"{kind}-saved-select", "value"),
        State(meta_id, "data"),
        prevent_initial_call=True,
    )
    def load_saved(filename, meta):
        if not filename or filename == meta["file"]:
            raise PreventUpdate
        record = sc.load(kind, filename)
        data = sc.to_store(kind, sc.reconcile(kind, record["data"], default))
        return data, sc.make_meta(filename, record), record["name"]

    @callback(
        Output(meta_id, "data", allow_duplicate=True),
        Input(f"{kind}-saved-name", "value"),
        State(meta_id, "data"),
        prevent_initial_call=True,
    )
    def rename(name, meta):
        if name is None or name == meta["name"]:
            raise PreventUpdate
        return {**meta, "name": name}

    @callback(
        Output(meta_id, "data", allow_duplicate=True),
        Output(f"{kind}-saved-select", "options"),
        Output(f"{kind}-saved-select", "value"),
        Output(f"{kind}-saved-name", "value", allow_duplicate=True),
        Input(f"{kind}-saved-save", "n_clicks"),
        State(store_id, "data"),
        State(meta_id, "data"),
        State(f"{kind}-saved-name", "value"),
        prevent_initial_call=True,
    )
    def save_clicked(n_clicks, data, meta, name):
        # Fires when the tab is rendered, as prevent_initial_call does not apply
        # to inputs inserted by another callback (render_page)
        if not n_clicks:
            raise PreventUpdate
        # Read the name from the input, in case the rename callback has not run yet
        meta = {**meta, "name": name if name is not None else meta["name"]}
        if not sc.is_dirty(data, meta):
            raise PreventUpdate
        _, meta = sc.save_if_changed(kind, data, meta)
        return meta, sc.list_saved(kind), meta["file"], meta["name"]

    @callback(
        Output(f"{kind}-saved-status", "children"),
        Input(store_id, "data"),
        Input(meta_id, "data"),
    )
    def update_status(data, meta):
        return get_status_badge(data, meta)
