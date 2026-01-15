from dash import html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF
import json
import os

### Workflow Functions ###

def load_workflows_from_file(filename):
    """Load workflows from a JSON file """
    with open(filename, 'r') as f:
        data = json.load(f)
    return data

def load_existing_rdf(filename):
    """Load existing RDF file"""
    g = Graph()
    g.parse(filename, format='ttl') ##Unsure which format to use in the future
    return g

def add_workflows_to_graph(graph, experiment_uuid, workflows):
    """Add Galaxy workflows to existing graph"""
    EX = Namespace("https://example.org/") 
    experiment_uri = URIRef(f"https://example.org/experiment/{experiment_uuid}")
    
    for workflow in workflows:
        workflow_uri = URIRef(f"https://example.org/workflow/{workflow['id']}")
        
        graph.add((workflow_uri, RDF.type, EX.Workflow))
        graph.add((workflow_uri, EX.name, Literal(workflow['name'])))
        graph.add((workflow_uri, EX.type, Literal(workflow['type'])))
        graph.add((workflow_uri, EX.url, URIRef(workflow['url'])))

        status_uri = URIRef(f"https://example.org/workflow/{workflow['id']}/status")
        graph.add((status_uri, EX.status, Literal("")))
        # Link to experiment
        graph.add((workflow_uri, EX.status, status_uri))
        graph.add((experiment_uri, EX.workflow, workflow_uri))
    
    return graph

def save_rdf(graph, filename):
    """Save RDF output to file"""
    rdf_bytes = graph.serialize(format='ttl')
    if isinstance(rdf_bytes, bytes):
        rdf_bytes = rdf_bytes.decode('utf-8')
    with open(filename, 'w') as f:
        f.write(graph.serialize(format='ttl'))

### UI Layout ###

def get_workflow_layout():
    """Create the Galaxy workflow UI layout"""
    
    # Load test workflows ## should be from galaxy api
    try:
        BASE_DIR = os.path.dirname(__file__)
        filename = os.path.join(BASE_DIR, 'test_files', 'galaxy_workflows.json')
        all_workflows = load_workflows_from_file(filename)
    except FileNotFoundError:
        all_workflows = []
    
    # Separate workflows  by online and post
    online_workflows = [w for w in all_workflows if w.get('type') == 'Online']
    postprocessing_workflows = [w for w in all_workflows if w.get('type') == 'Post-processing']
    
    # Scan folder for NT/TTL files
    BASE_DIR = os.path.dirname(__file__)
    nt_FOLDER = os.path.join(BASE_DIR, 'test_files')
    rdf_files = [f for f in os.listdir(nt_FOLDER) if f.endswith((".ttl"))]
    dropdown_options = [{"label": f, "value": f} for f in rdf_files]

    return dbc.Container([
        html.H3("Galaxy Workflows"),
        
        html.Label("Experiment UUID:"),
        dcc.Dropdown(
            id='nt-dropdown',
            options=dropdown_options,
            value=rdf_files[0] if rdf_files else None,
            clearable=False,
            style={'marginBottom': '20px'}
        ),
    
        html.Br(),
        
        html.Label("Online:"),
        dcc.Dropdown(
            id='workflow-online',
            options=[{'label': w['name'], 'value': w['id']} for w in online_workflows],
            placeholder='Select online workflow',
            multi=True
        ),
        
        html.Br(),
        
        html.Label("Post-processing:"),
        dcc.Dropdown(
            id='workflow-postprocessing',
            options=[{'label': w['name'], 'value': w['id']} for w in postprocessing_workflows],
            placeholder='Select post-processing workflow',
            multi=True
        ),
        
        html.Br(),
        
        dbc.Button("Add Workflows to RDF", id="add-workflows-btn", color="success"),
        
        html.Br(),
        html.Br(),
        
        html.Div(id="workflow-status")
    ])


def register_workflow_callbacks(app):
    """Register callbacks for workflow management"""
    
    @app.callback(
        Output('workflow-status', 'children'),
        Input('add-workflows-btn', 'n_clicks'),
        State('nt-dropdown', 'value'),
        State('workflow-online', 'value'),
        State('workflow-postprocessing', 'value'),
        prevent_initial_call=True
    )
    def add_workflows(n_clicks, selected_file, online_ids, postproc_ids):
        if not selected_file:
            return html.Div("Please select an experiment", style={'color': 'red'})

        # Extract 4-digit UUID from selected file
        import re
        match = re.search(r'(\d+)', selected_file)
        if not match:
            return html.Div("Cannot parse experiment UUID from file", style={'color': 'red'})
        uuid_formatted = match.group(1)

        BASE_DIR = os.path.dirname(__file__)
        rdf_filename = os.path.join(BASE_DIR, 'test_files', selected_file)
        g = load_existing_rdf(rdf_filename)

        # Filter workflows
        selected_ids = (online_ids or []) + (postproc_ids or [])
        all_workflows = load_workflows_from_file(os.path.join(BASE_DIR, 'test_files', 'galaxy_workflows.json'))
        selected_workflows = [w for w in all_workflows if w['id'] in selected_ids]

        if not selected_workflows:
            return html.Div("No matching workflows found", style={'color': 'red'})

        g = add_workflows_to_graph(g, uuid_formatted, selected_workflows)
        save_rdf(g, rdf_filename)

                