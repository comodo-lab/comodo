from dash import html
import dash_bootstrap_components as dbc


def status_item(item_name):
    status_item = dbc.Col([
        dbc.Row(html.H3(item_name)),
        dbc.Row(html.H4(f"{item_name} status"))
    ])
    return status_item

def get_status_card(header, title, text, status):
    card = dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody([
            html.H4(title, className="card-title"),
            html.P(text, className="card-text"),
        ])
    ], color=status, inverse=True)
    return card

def get_header_bar():
    header_bar = dbc.CardGroup([
        dbc.Card([
            dbc.CardHeader(""),
            dbc.CardBody([
                html.H1("Comodo Lab", className="card-title"),
            ])
        ], color="dark", inverse=True),
        get_status_card("Control System Status", "bad", "15:00:01", "danger"),
        get_status_card("Experiment ID", "ABC-123", "14:44:24", "dark"),
        get_status_card("Adjusting", "t_left,t_right", "15:00:01", "success")
    ])
    return header_bar
