from dash import html, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

import dash_ag_grid as dag

from src.config_loader import PID_NAME_MAP

# Parameters where None is a valid value
NULLABLE = ["max_rate"]


def to_spc_config(rows):
    """
    Returns the config of each spc as a dict of {name: {"pid": {k_p, k_i, k_d...}}}.
    Raises a ValueError if any non-nullable parameter is not a number.
    """
    config = {}
    for row in rows or []:
        pid = {}
        for key in PID_NAME_MAP:
            value = row.get(key)
            if value is None and key in NULLABLE:
                pid[key] = None
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                pid[key] = float(value)
            else:
                raise ValueError(
                    f"Invalid {PID_NAME_MAP[key]} for setpoint controller "
                    f"'{row.get('name')}': {value!r}. PID parameters must be numbers."
                )
        config[row["name"]] = {"pid": pid}
    return config


def get_spc_setup(data=[]):
    """
    Creates a dash-ag-grid component to edit the PID parameters of each setpoint controller.
    """
    component_id = "spc_setup"

    pid_columns = [
        {"headerName": name, "field": key, "cellDataType": "number"}
        for key, name in PID_NAME_MAP.items()
    ]
    name_column = {
        "headerName": "Setpoint controller",
        "field": "name",
        "editable": False,
        "minWidth": 300,
    }

    layout = [
        html.P(
            "PID parameters sent to the setpoint controllers when an experiment "
            "starts. All of them are required, except the max rate of change "
            "(empty means no limit)."
        ),
        dbc.Row(
            [
                dag.AgGrid(
                    id=component_id,
                    columnDefs=[name_column] + pid_columns,
                    rowData=data,
                    className="ag-theme-alpine",
                    defaultColDef={"editable": True, "resizable": True},
                    columnSize="responsiveSizeToFit",
                    dashGridOptions={"domLayout": "autoHeight"},
                )
            ]
        ),
    ]

    return html.Div(layout, id="spc-setup-container")


@callback(Output("spc_setup", "rowData"), Input("spc-store", "data"))
def update_table(data):
    return data


@callback(
    Output("spc-store", "data"),
    Input("spc_setup", "cellValueChanged"),
    State("spc_setup", "rowData"),
    prevent_initial_call=True,
)
def sync_edits_to_store(cell_change, current_rows):
    if not cell_change:
        raise PreventUpdate
    return current_rows
