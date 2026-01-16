from librti_model import LibrtiSystem
from linkml_runtime.loaders import yaml_loader
from linkml_runtime.dumpers import json_dumper
from linkml.generators.jsonldcontextgen import ContextGenerator
from rdflib import Graph
import json
import os

def generate_initial_rdf(UUID):
    """Generate RDF from YAML configuration"""
    exp = yaml_loader.load("librti.yaml", target_class=LibrtiSystem)

    json_str = json_dumper.dumps(exp, inject_type=True)
    json_obj = json.loads(json_str)

    context_str = ContextGenerator("librti.yaml.schema", metadata=False).serialize()
    context = json.loads(context_str)

    json_obj['@context'] = context['@context']
    json_obj['@id'] = f'https://example.org/LibrtiSystem/{UUID}'

    jsonld_str = json.dumps(json_obj, indent=2)

    # Parse as RDF
    g = Graph()
    g.parse(data=jsonld_str, format='json-ld')
    rdf_output = g.serialize(format='ttl')

    return rdf_output

def save_rdf(rdf_output, name):
    """Save RDF output to file"""
    with open(name, 'w') as f:
        f.write(rdf_output)

def main(UUID):
    rdf_output = generate_initial_rdf(UUID)
    base_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(base_dir, ".."))  # .../comodo
    output_dir = os.path.join(project_root, "ui", "test_files") ## temp folder for ttl

    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(output_dir, f"LibrtiSystem_{UUID}.ttl")

    save_rdf(rdf_output, filename)
    print(f"Saved RDF to {filename}")

if __name__ == '__main__':  

    ##Input experiment UUID
    ##Output RDF from experimental config
    main(UUID=f'{1:04d}') 