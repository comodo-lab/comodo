from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, no_update, ctx
import dash_bootstrap_components as dbc
import plotly.express as px
import uuid
import json

import dash_ag_grid as dag

import pandas as pd
import plotly.graph_objects as go

from utils.mqtt_clients import MQTTPublisher

def get_control_panel():
    layout = html.Div([
        dbc.Button("Start experiment", color="success", id="submit-experiment"),
    ],
    className="d-grid gap-2",
    )
    return layout

@callback(
    Output('hidden-div', 'children'),
    Input('submit-experiment', 'n_clicks'),
    State("experiment-designer-store", "data"),
    State('sensor-store', 'data'),
    prevent_initial_call=True
)
def update_output(n_clicks, table_data, sensors):
    if n_clicks == 0:
        raise PreventUpdate
        
    # Prepare data for transmission
    experiment_id = str(uuid.uuid4())[:8]

    experiment_config = {
        "uid": experiment_id,
        "config": {
            "resolution": sensors[0].get("resolution", 1.0),
            "sensors": sensors
        },
        "experiment": table_data
    }
    json_data = json.dumps(experiment_config).encode("utf-8")

    print(f"Data: {json_data}")
    # Publish data
    client = MQTTPublisher.get_instance()
    client.publish("ui/start", json_data)
    return None


def get_control_window(params=[]):
    """
    Creates the control window for the experiment designer.
    """
    if not params:
        raise ValueError("Parameter list cannot be empty. Please provide at least one parameter.")

    control_rows = [
        dbc.Row(html.H2("Control Window")),
    ]

    for param in params:
        param_name = param['name']
        param_min = param.get('min', 0)
        param_max = param.get('max', 100)
        param_step = param.get('step', 1)

        control_rows.append(
            html.H4(f"Control: {' '.join(w.capitalize() for w in param_name.split('_'))}")
        )
        control_rows.append(
            get_control_component(
                param_name=param_name,
                min_val=param_min,
                max_val=param_max,
                step=param_step
            )
        )

    # Define the layout of the control window
    control_window = dbc.Container(control_rows, fluid=True)

    return control_window


def get_control_component(param_name=None, min_val=0, max_val=100, step=1):
    """
    Returns the control component for the experiment designer.
    Includes a slider and a readout for current setpoint and actual value.
    """
    if param_name is None:
        return html.Div(
            [
                html.H4("No Parameter Selected"),
            ],
            id="control-component-no-param"
        )

    control_component = dbc.Container([
        dbc.Row([
            dbc.Col(
                dcc.Slider(
                    id="control-slider",
                    min=min_val,
                    max=max_val,
                    step=step,
                    value=(min_val + max_val) // 2,
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
            ),
            dbc.Col(
                dcc.Graph(
                    id={"type": "control-gauge-combined", "param": param_name},
                    figure=make_combined_gauge(
                        setpoint=(min_val + max_val) // 2,
                        current=(min_val + max_val) // 2,
                        min_val=min_val,
                        max_val=max_val,
                        param=param_name
                    ),
                    config={"displayModeBar": False}
                ),
                width=6
            )
        ])
    ])

    return control_component


def make_combined_gauge(setpoint, current, min_val=0, max_val=100, param="temp"):
    fig = go.Figure()

    # Main gauge with no dominant bar
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=current,
        title={"text": f"{param.capitalize()} - Current Value"},
        gauge={
            "axis": {"range": [min_val, max_val]},
            "bar": {"color": "lightgray", "thickness": 0.2},
            "steps": [
                {"range": [min_val, max_val], "color": "white"}
            ],
        },
        domain={"x": [0, 1], "y": [0, 1]}
    ))

    # Add a line to represent the setpoint on the gauge
    angle = (setpoint - min_val) / (max_val - min_val) * 180
    radius = 0.5

    import math
    x_center, y_center = 0.5, 0.5
    x = x_center + radius * math.cos(math.radians(180 - angle))
    y = y_center + radius * math.sin(math.radians(180 - angle))

    fig.add_trace(go.Scatter(
        x=[x],
        y=[y],
        mode="markers+text",
        marker=dict(symbol="line-ns-open", size=20, color="red", line=dict(width=4)),
        text=[f"Setpoint: {setpoint}"],
        textposition="top center",
        showlegend=False,
        hoverinfo="text"
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=300,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )

    return fig
