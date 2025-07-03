from dash import html
import dash_bootstrap_components as dbc


def status_item(item_name):
    status_item = dbc.Col([
        dbc.Row(html.H3(item_name)),
        dbc.Row(html.H4(f"{item_name} status"))
    ])
    return status_item


def get_header_bar():
    header_bar = dbc.Container([
        dbc.Row(html.H1("Experiment status")),
        dbc.Row([
            status_item("Control System Status"),
            status_item("Experiment ID"),
            status_item("Adjusting"),
        ])
        ],

        fluid=True,
        className="p-4 bg-light rounded",
    )

    return header_bar
