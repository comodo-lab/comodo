from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px

import dash_ag_grid as dag
from dash import Dash, html

app = Dash(
    external_stylesheets=[dbc.themes.LUX]
)

columnDefs = [
    {"field": "country"},
    {
        "headerName": "Select Editor",
        "field": "city",
        "editable": True,
        "cellEditor": "agSelectCellEditor",
        "cellEditorParams": {
            "values": ["red", "yellow", "green"],
        }
    },

]

rowData = [
    {"country": "United States", "city": "Boston"},
    {"country": "Canada", "city": "Montreal"},
    {"country": "Canada", "city": "Vancouver"},
]

app.layout = html.Div(
    [
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
        dbc.Row([
            dbc.Col(
                dag.AgGrid(
                    id="editing-grid",
                    columnDefs=columnDefs,
                    rowData=rowData,
                    className="ag-theme-alpine-auto-dark",
                    columnSize="sizeToFit",
                    defaultColDef={"editable": True},
                ),
            ),
            dbc.Col(
                html.Div(id="editing-grid-output"),
            )
        ])
    ]
)

@callback(
    Output("editing-grid-output", "children"),
    Input("editing-grid", "cellValueChanged")
)
def update(cell_changed):
    return f"{cell_changed}"

if __name__ == "__main__":
    app.run(debug=True,
            host='0.0.0.0'
            )

