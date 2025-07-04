from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import plotly.express as px

import dash_ag_grid as dag
from dash import Dash, html

app = Dash(
    external_stylesheets=[dbc.themes.LUX]
)

PARAMS = [
    'temp_left',
    'temp_main',
    'temp_right'
]

rowData = []
baseRow = {}
columnDefs = []
for param in PARAMS:
    column = {
        "headerName": param,
        "field": param,
    }
    column_profile = {
        "headerName": f"{param} profile",
        "field": "Linear",
        "cellEditor": "agSelectCellEditor",
        "cellEditorParams": {
            "values": ["Linear", "Exponential", "The other one"],
        }
    }
    columnDefs.append(column)
    columnDefs.append(column_profile)
    baseRow[param] = "2"
    baseRow[f"{param} profile"] = "Linear"
    
#rowData = [
#    {"country": "United States", "city": "Boston"},
#    {"country": "Canada", "city": "Montreal"},
#    {"country": "Canada", "city": "Vancouver"},
#]

rowData = [baseRow]

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
                dcc.Graph(id='experiment-plot')
            )
        ])
    ]
)

@callback(
    Output("experiment-plot", "figure"),
    Input("editing-grid", "cellValueChanged")
)
def update(cell_changed):
    if cell_changed is None:
        return
    
    new_data = cell_changed[0]['data']
    y = []
    for param in PARAMS:
        y.append(new_data[param])
    fig = px.scatter(x=[0, 1, 2], y=y)
    return fig

if __name__ == "__main__":
    app.run(debug=True,
            host='0.0.0.0'
            )

