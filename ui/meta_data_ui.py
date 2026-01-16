import dash_cytoscape as cyto
from dash import html, dcc, Input, Output, callback
from rdflib import Graph, URIRef, Namespace, Literal
import os

def get_metadata_layout():
    BASE_DIR = os.path.dirname(__file__)
    nt_FOLDER = os.path.join(BASE_DIR, 'test_files')

    # Scan folder for NT/TTL files
    rdf_files = [f for f in os.listdir(nt_FOLDER) if f.endswith((".ttl"))]
    dropdown_options = [{"label": f, "value": f} for f in rdf_files]

    # Define namespaces
    EX = Namespace("https://example.org/") #Needs to be fixed to actual 

    def get_local_name(uri):
        """Extract the local name from a URI"""
        return str(uri).split('/')[-1].split('#')[-1]
    
    def remove_underscores(elements):
        for element in elements:
            if 'label' in element.get('data', {}):
                label_new = element['data']['label'].replace("_", " ")
                element['data']['label'] = label_new
        
        return elements

    
    def rdf_to_top_level_elements(rdf_filename):
        """Parse RDF and extract sensor etc for ROOT type experiment nodes"""
        g = Graph()
        rdf_path = os.path.join(nt_FOLDER, rdf_filename)
        
        # Determine format
        format_type = "ttl" if rdf_filename.endswith(".ttl") else "turtle"
        g.parse(rdf_path, format=format_type)

        nodes = {}
        edges = []

        # Find the experiment node (type Experiment)
        ROOT_TYPES = {
            "https://example.org/Experiment", ##Example for each experiment
            "https://example.org/LibrtiSystem" ##Example for each experiment
        }

        experiment_uri = None
        for s, p, o in g:
            if str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and str(o) in ROOT_TYPES:
                experiment_uri = s
                break

        if not experiment_uri:
            return []

        # Add experiment node
        exp_id = str(experiment_uri)
        exp_label = get_local_name(exp_id)
            
        nodes[exp_id] = {
            'data': {
                'id': exp_id,
                'label': exp_label,
                'type': 'experiment',
                'category': 'experiment'
            }
        }

        # Top-level predicates we care about
        top_level_predicates = [
            str(EX.instruments),
            str(EX.visualisations),
            str(EX.workflow),
            str(EX.emulators),
            str(EX.globel_set),
        ]

        # Track instruments to get their sensors later
        instrument_nodes = []

        # Find direct connections from experiment
        for s, p, o in g:
            if str(s) == exp_id and str(p) in top_level_predicates:
                pred_name = get_local_name(str(p))
                
                if isinstance(o, URIRef):
                    # Direct URI object (like workflow)
                    o_id = str(o)
                    
                    # Determine node type and label
                    node_type = 'workflow' if 'workflow' in o_id else 'other'
                    node_label = get_local_name(o_id)
                    
                    # Get additional info for workflows
                    if node_type == 'workflow':
                        for s2, p2, o2 in g:
                            if str(s2) == o_id:
                                if str(p2) == str(EX.name):
                                    node_label = str(o2)
                                    break
                    
                    nodes[o_id] = {
                        'data': {
                            'id': o_id,
                            'label': node_label,
                            'type': node_type,
                            'category': 'workflow'
                        }
                    }
                    
                    edges.append({
                        'data': {
                            'source': exp_id,
                            'target': o_id,
                            'label': pred_name
                        }
                    })
                else:
                    # Blank node - need to explore one level deeper
                    blank_id = str(o)
                    
                    # Determine category from predicate
                    if pred_name == 'instruments':
                        category = 'instrument'
                    elif pred_name == 'visualisations':
                        category = 'visualisation'
                    elif pred_name == 'emulators':
                        category = 'emulator'   
                    else:
                        category = 'other'
                    
                    # Find what's connected to this blank node
                    children = []
                    for s2, p2, o2 in g:
                        if str(s2) == blank_id and isinstance(o2, URIRef):
                            child_id = str(o2)
                            child_label = get_local_name(child_id)
                            child_type = get_local_name(str(p2))
                            
                            children.append({
                                'id': child_id,
                                'label': child_label,
                                'type': child_type,
                                'category': category
                            })
                    
                    # Create nodes for each child
                    for child in children:
                        nodes[child['id']] = {
                            'data': {
                                'id': child['id'],
                                'label': child['label'],
                                'type': child['type'],
                                'category': child['category']
                            }
                        }
                        
                        edges.append({
                            'data': {
                                'source': exp_id,
                                'target': child['id'],
                                'label': pred_name
                            }
                        })
                        
                        # Track instruments for sensor extraction
                        if category == 'instrument':
                            instrument_nodes.append(child['id'])
                # After adding workflow nodes
        workflow_nodes = [nid for nid, n in nodes.items() if n['data']['category'] == 'workflow']

        # Add status nodes for workflows
        for workflow_id in workflow_nodes:
            # Find the blank node that connects to status
            for s, p, o in g:
                if str(s) == workflow_id and str(p) == str(EX.status):
                    status_blank = str(o)
                    
                    # Find literal connected to this blank node
                    for s2, p2, o2 in g:
                        if str(s2) == status_blank and isinstance(o2, Literal):
                            status_value = str(o2)  # "pass" or "fail"
                            
                            # Create unique node ID
                            status_node_id = workflow_id + "_status"
                            if status_value == "":
                                continue
                            
                            nodes[status_node_id] = {
                                'data': {
                                    'id': status_node_id,
                                    'label': status_value,
                                    'type': 'status',
                                    'category': 'fail' if status_value == 'fail' else 'pass'
                                }
                            }
                            
                            # Connect workflow -> status
                            edges.append({
                                'data': {
                                    'source': workflow_id,
                                    'target': status_node_id,
                                    'label': 'status'
                                }
                            })
                            
                            break  
                    break  

        #find sensors for each instrument
        for instrument_id in instrument_nodes:
            #find the blank node that connects to sensors
            for s, p, o in g:
                if str(s) == instrument_id and str(p) == str(EX.sensors):
                    sensors_blank = str(o)
                    
                    #find all sensors connected to this blank node
                    for s2, p2, o2 in g:
                        if str(s2) == sensors_blank and isinstance(o2, URIRef):
                            sensor_id = str(o2)
                            sensor_label = get_local_name(sensor_id)
                            
                            #add sensor node
                            nodes[sensor_id] = {
                                'data': {
                                    'id': sensor_id,
                                    'label': sensor_label,
                                    'type': 'sensor',
                                    'category': 'sensor'
                                }
                            }
                            
                            #connect sensor to instrument
                            edges.append({
                                'data': {
                                    'source': instrument_id,
                                    'target': sensor_id,
                                    'label': 'has_sensor'
                                }
                            })

        return list(nodes.values()) + edges

    # Initial elements for the first file (if exists)
    initial_elements = rdf_to_top_level_elements(rdf_files[0]) if rdf_files else []
    layout = html.Div([
        html.H2("Experiment Overview"),
        html.P("Top-level view showing experiment connections to instruments, workflows, visualizations, and sensors"),
        
        dcc.Dropdown(
            id='nt-dropdown',
            options=dropdown_options,
            value=rdf_files[0] if rdf_files else None,
            clearable=False,
            style={'marginBottom': '20px'}
        ),
        
        cyto.Cytoscape(
            id='kg-graph',
            elements=initial_elements,
            style={'width': '100%', 'height': '700px', 'border': '1px solid #ddd'},
            layout={
                'name': 'cose',
                'padding': 200,
                'initialTemp': 100000,
                'animate': True
            },
            stylesheet=[
                # Default for all nodes
                {
                    'selector': 'node',
                    'style': {
                        'label': 'data(label)',
                        'background-color': '#AAAAAA',
                        'color': 'white',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 60,
                        'height': 60,
                        'font-size': '10px',
                        'text-wrap': 'wrap',
                        'text-max-width': '55px'
                    }
                },
                # Experiment node
                {
                    'selector': '[category="experiment"]',
                    'style': {
                        'background-color': '#FF4136',
                        'width': 100,
                        'height': 100,
                        'font-size': '14px',
                        'font-weight': 'bold'
                    }
                },
                # Workflow nodes
                {
                    'selector': '[category="workflow"]',
                    'style': {
                        'background-color': "#BAD61C",
                        'width': 70,
                        'height': 70,
                        'font-size': '11px'
                    }
                },
                # All instrument nodes
                {
                    'selector': '[category="instrument"]',
                    'style': {
                        'background-color': '#0074D9',
                        'width': 70,
                        'height': 70,
                        'font-size': '11px'
                    }
                },
                # All visualization nodes
                {
                    'selector': '[category="visualisation"]',
                    'style': {
                        'background-color': '#FF851B',
                        'width': 70,
                        'height': 70,
                        'font-size': '11px'
                    }
                },
                {
                    'selector': '[category="emulator"]',
                    'style': {
                        'background-color': '#00CED1',  # turquoise
                        'width': 70,
                        'height': 70,
                        'font-size': '11px'
                    }
                },
                # Sensor nodes (smaller, purple)
                {
                    'selector': '[category="sensor"]',
                    'style': {
                        'background-color': '#B10DC9',
                        'width': 60,
                        'height': 60,
                        'font-size': '9px'
                    }
                },               
                ## Pass node 
                {
                    'selector': '[category="pass"]',
                    'style': {
                        'background-color': "#2ECC40",
                        'width': 60,
                        'height': 60,
                        'font-size': '9px'
                    }
                },
                 ## fail node 
                {
                    'selector': '[category="fail"]',
                    'style': {
                        'background-color': "#D12F2F",
                        'width': 60,
                        'height': 60,
                        'font-size': '9px'
                    }
                },
                # Edges
                {
                    'selector': 'edge',
                    'style': {
                        'label': 'data(label)',
                        'line-color': '#666',
                        'target-arrow-color': '#666',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'font-size': '8px',
                        'text-rotation': 'autorotate',
                        'text-margin-y': -10
                    }
                }
            ]
        )
    
    ])
    
    # Callback to update graph when dropdown changes
    @callback(
        Output('kg-graph', 'elements'),
        Input('nt-dropdown', 'value')
    )
    def update_graph(selected_file):
        if selected_file and selected_file in rdf_files:
            elements = rdf_to_top_level_elements(selected_file)
            return remove_underscores(elements) 
        return []

    return layout