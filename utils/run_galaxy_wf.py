from rdflib import Graph, Namespace, URIRef, Literal
import os
import random

### Should be in Randal
def mock_wf():
    """ Mock workflow execution  """
    result = random.choice(['pass', 'fail'])
    return result


def check_galaxy_workflows(experiment_uuid):
    """
    Check Galaxy workflows and add status to RDF graph
    
    Args:
        experiment_uuid: UUID of the experiment (e.g., '0001')
    """
    BASE_DIR = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(BASE_DIR, ".."))  # .../comodo
    output_dir = os.path.join(project_root, "ui", "test_files") ## temp folder for ttl
    
    # Construct filename from UUID
    rdf_filename = os.path.join(output_dir, f'experiment_{experiment_uuid}.nt')
    
    # Load RDF
    g = Graph()
    g.parse(rdf_filename, format='nt')
    
    # Define namespaces
    EX = Namespace("https://example.org/")
    
    # Find experiment URI
    experiment_uri = f"https://example.org/experiment/{experiment_uuid}"
    
    # Find all workflows connected to this experiment
    workflow_results = []
    
    for s, p, o in g:
        if str(s) == experiment_uri and str(p) == str(EX.workflow):
            workflow_uri = o  # Keep as URIRef, not string
            
            # Get workflow details
            workflow_name = None
            workflow_type = None
            workflow_url = None
            
            for s2, p2, o2 in g:
                if str(s2) == str(workflow_uri):
                    if str(p2) == str(EX.name):
                        workflow_name = str(o2)
                    elif str(p2) == str(EX.type):
                        workflow_type = str(o2)
                    elif str(p2) == str(EX.url):
                        workflow_url = str(o2)
            
            ### Mock galaxy run
            if workflow_url: 
                result = mock_wf()  
                
                # Add status directly to workflow URI
                g.add((URIRef(f'{workflow_uri}/status'), EX.status, Literal(result)))

                
                workflow_results.append({
                    'name': workflow_name,
                    'type': workflow_type,
                    'url': workflow_url,
                    'status': result
                })
    
  
    with open(rdf_filename, 'w') as f:
        f.write(g.serialize(format='nt'))


# Example usage
if __name__ == '__main__':
    result = check_galaxy_workflows('0002')
