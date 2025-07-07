from dash import html
import dash_bootstrap_components as dbc


def status_item(item_name):
    status_item = dbc.Col([
        dbc.Row(html.H3(item_name)),
        dbc.Row(html.H4(f"{item_name} status"))
    ])
    return status_item

def get_status_card(header, title, text, status):
    card = dbc.Col([dbc.Card([
        dbc.CardHeader(header),
        dbc.CardBody([
            html.H4(title, className="card-title"),
            html.P(text, className="card-text"),
        ])
    ], color=status, inverse=True)])
    return card

def get_header_bar():
    header_bar = dbc.Container([
        html.Hr(),
        html.H3("System status"),
        dbc.Row([
            get_status_card("Control System Status", "bad", "15:00:01", "danger"),
            get_status_card("Experiment ID", "ABC-123", "14:44:24", "dark"),
            get_status_card("Adjusting", "t_left,t_right", "15:00:01", "success")
        ]),
        html.Hr(),
    ], fluid=True)
    return header_bar

def get_nav_bar():
    navbar = dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("Designer", href="#")),
            dbc.NavItem(dbc.NavLink("Controls", href="#")),
        ],
        brand="Comodo-Lab",
        brand_href="#",
        color="primary",
        dark=True,
        links_left=True,
        sticky=True,
        fluid=True,
        brand_style={
            "fontSize": "2rem",
            "fontWeight": "bold",
        },
    )
    return navbar
