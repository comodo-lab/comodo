from dash import (
    html,
    dcc,
    callback,
    Output,
    Input,
    State,
    no_update,
    ctx,
)
import dash_bootstrap_components as dbc
import uuid
import json
import base64

import dash_ag_grid as dag

import plotly.graph_objects as go

from plot import plot_data_plotly


PROFILES = ["linear", "logarithmic", "exponential", "step"]

_active_params = []


def get_experiment_designer(data=[], params=[]):
    global _active_params
    _active_params = params

    component_id = "experiment-designer"

    columns = ["time"]
    for col in params:
        columns.append(col)
        columns.append(f"{col}_profile")

    for row in data:
        if "id" not in row:
            row["id"] = str(uuid.uuid4())

    column_dicts = [
        {"headerName": " ".join(w.capitalize() for w in col.split("_")), "field": col}
        for col in columns
    ]

    for col in column_dicts:
        if col["field"] == "time":
            col.update({"headerName": "Time (s)", "checkboxSelection": True})
        if col["field"].endswith("_profile"):
            col.update(
                {
                    "headerName": "Profile",
                    "cellEditor": "agSelectCellEditor",
                    "cellEditorParams": {"values": PROFILES},
                }
            )

    column_dicts.insert(0, {"field": "id", "hide": True})

    layout = [
        dbc.Row(
            [
                dag.AgGrid(
                    id=component_id,
                    columnDefs=column_dicts,
                    rowData=data,
                    className="ag-theme-alpine",
                    defaultColDef={"editable": True, "resizable": True},
                    columnSize="responsiveSizeToFit",
                    getRowId="params.data.id",
                    dashGridOptions={
                        "rowSelection": "multiple",
                        "suppressRowClickSelection": True,
                        "domLayout": "autoHeight",
                    },
                )
            ]
        ),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-plus-lg me-1"), "Add Row"],
                        id=f"{component_id}-add", n_clicks=0, color="success",
                    ),
                    className="d-grid",
                ),
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-trash me-1"), "Delete"],
                        id=f"{component_id}-delete", n_clicks=0, color="danger",
                    ),
                    className="d-grid",
                ),
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-download me-1"), "Save"],
                        id="experiment-save-designer", n_clicks=0, color="primary",
                    ),
                    className="d-grid",
                ),
                dbc.Col(
                    dcc.Upload(
                        dbc.Button(
                            [html.I(className="bi bi-upload me-1"), "Load"],
                            color="primary", style={"width": "100%"},
                        ),
                        id="experiment-load-designer",
                        accept=".json",
                        style={"width": "100%"},
                    ),
                    className="d-grid",
                ),
            ],
            className="g-2 mt-1",
        ),
    ]

    return html.Div(layout, id="experiment-designer-container")


def get_experiment_graph():
    return dcc.Graph(id="experiment-plot", responsive=True)


@callback(
    Output("experiment-designer", "rowTransaction"),
    Input("experiment-designer-add", "n_clicks"),
    Input("experiment-designer-delete", "n_clicks"),
    State("experiment-designer", "rowData"),
    State("experiment-designer", "selectedRows"),
    prevent_initial_call=True,
)
def modify_rows(add_clicks, delete_clicks, current_rows, selected_rows):
    trigger = ctx.triggered_id
    if trigger == "experiment-designer-add":
        current_rows = current_rows or []
        new_row = {"id": str(uuid.uuid4())}
        template = current_rows[0] if current_rows else {}
        for col in template:
            if col == "id":
                continue
            elif col.endswith("_profile"):
                new_row[col] = PROFILES[0]
            else:
                new_row[col] = 0.0 if col != "time" else 0
        last_time = max(
            (row.get("time", 0) for row in current_rows if isinstance(row.get("time"), (int, float))),
            default=0,
        )
        new_row["time"] = last_time + 30
        return {"add": [new_row]}

    if trigger == "experiment-designer-delete":
        if not selected_rows:
            return no_update
        return {"remove": selected_rows}

    return no_update


@callback(
    Output("experiment-designer-store", "data"),
    Input("experiment-designer", "virtualRowData"),
    Input("experiment-designer", "cellValueChanged"),
    State("experiment-designer", "rowData"),
    prevent_initial_call=True,
)
def sync_to_store(virtual_rows, _cell_change, row_data):
    rows = virtual_rows or row_data or []
    if not rows:
        return no_update
    return sorted(rows, key=lambda r: r.get("time", 0))


@callback(
    Output("save-trigger", "data", allow_duplicate=True),
    Input("experiment-save-designer", "n_clicks"),
    prevent_initial_call=True,
)
def trigger_save_designer(n):
    if not n:
        return no_update
    return n


@callback(
    Output("experiment-download", "data"),
    Input("save-trigger", "data"),
    State("experiment-designer-store", "data"),
    State("instrument-store", "data"),
    State("experiment-config-store", "data"),
    prevent_initial_call=True,
)
def save_all(trigger, exp_data, inst_data, cfg_data):
    export = {
        "experiment": [{k: v for k, v in row.items() if k != "id"} for row in (exp_data or [])],
        "instruments": inst_data or [],
        "config": cfg_data or [],
    }
    return dcc.send_string(json.dumps(export, indent=2), "experiment.json")


def _parse_load(contents):
    _, encoded = contents.split(",", 1)
    return json.loads(base64.b64decode(encoded).decode("utf-8"))


@callback(
    Output("experiment-designer", "rowData"),
    Output("experiment-designer-store", "data", allow_duplicate=True),
    Output("instrument-store", "data", allow_duplicate=True),
    Output("experiment-config-store", "data", allow_duplicate=True),
    Input("experiment-load-designer", "contents"),
    prevent_initial_call=True,
)
def load_from_designer(contents):
    if not contents:
        return no_update, no_update, no_update, no_update
    try:
        loaded = _parse_load(contents)
        exp_rows, inst_rows, cfg_rows = _split_load(loaded)
        for row in exp_rows:
            row["id"] = str(uuid.uuid4())
        return exp_rows, exp_rows, inst_rows, cfg_rows
    except Exception:
        return no_update, no_update, no_update, no_update


def _split_load(loaded):
    if isinstance(loaded, dict):
        exp = loaded.get("experiment", [])
        inst = loaded.get("instruments", no_update)
        cfg = loaded.get("config", no_update)
    else:
        exp = loaded if isinstance(loaded, list) else []
        inst = no_update
        cfg = no_update
    return exp, inst, cfg


@callback(
    Output("experiment-plot", "figure"),
    Input("experiment-designer-store", "data"),
)
def update_figure(data):
    if not data:
        return go.Figure()
    try:
        return plot_data_plotly(data, xlabel="Time (s)")
    except Exception as e:
        print(f"Error plotting experiment data: {e}")
        return go.Figure()
