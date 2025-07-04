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
        dbc.Row(html.H1("Comodo-Lab")),
        dbc.Row(
            dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Control System Status"),
                        html.Th("Experiment ID"),
                        html.Th("Adjusting"),
                    ]),
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td("Running"),
                        html.Td("ABC-123"),
                        html.Td("Temp1, Temp2")
                    ]),
                ]),
            ]),
        ),
        ],

        fluid=True,
        className="p-4 bg-light rounded",
    )

    return header_bar
