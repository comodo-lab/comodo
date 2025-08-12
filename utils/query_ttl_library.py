import tkinter as tk
from tkinter import ttk
import rdflib
from rdflib import Literal, ConjunctiveGraph, Graph, URIRef

# --- Load RDF Named Graphs --- ## Add fuseki support here
dataset = ConjunctiveGraph()
graph_files = {
    "graph1": "GDPS_1.ttl",
    "graph2": "GDPS_2.ttl",
    "graph3": "GDPS_3.ttl",
    "graph4": "GDPS_4.ttl"
    
}

for name, file in graph_files.items():
    uri = URIRef(f"http://example.org/{name}")
    g = Graph(dataset.store, uri)
    g.parse(file, format="ttl")

# --- Utilities ---
def get_local_name(uri):
    return str(uri).split('/')[-1].split('#')[-1]

def get_unique_subjects():
    query = "SELECT DISTINCT ?s WHERE { GRAPH ?g { ?s ?p ?o . } }"
    results = dataset.query(query)
    return sorted(set(get_local_name(row.s) for row in results if row.s))

def get_predicates_for_subject(subject_local):
    query = f"""
    SELECT DISTINCT ?p WHERE {{
        GRAPH ?g {{ <http://example.org/{subject_local}> ?p ?o . }}
    }}
    """
    results = dataset.query(query)
    return sorted(set(get_local_name(row.p) for row in results if row.p))

def get_objects_for_predicate(subject_local, predicate_local):
    query = f"""
    SELECT DISTINCT ?o WHERE {{
        GRAPH ?g {{
            <http://example.org/{subject_local}> <http://schema.org/{predicate_local}> ?o .
        }}
    }}
    """
    results = dataset.query(query)
    return sorted(set(str(row.o) for row in results if row.o))

def find_matching_graphs(filters):
    where_clauses = ""
    for subj, (pred, val) in filters.items():
        if not (pred and val):
            continue
        subj_uri = f"<http://example.org/{subj}>"
        pred_uri = f"<http://schema.org/{pred}>"
        val_lit = Literal(val).n3()
        where_clauses += f"{subj_uri} {pred_uri} {val_lit} .\n"
    if not where_clauses:
        return []
    query = f"""
    PREFIX schema: <http://schema.org/>
    SELECT DISTINCT ?g WHERE {{
        GRAPH ?g {{
            {where_clauses}
        }}
    }}
    """
    return [row.g for row in dataset.query(query)]

def get_all_experiment_related_predicates():
    query = """
    PREFIX schema: <http://schema.org/>
    SELECT DISTINCT ?p WHERE {
        GRAPH ?g {
            {
                ?exp a schema:Experiment ;
                     ?p ?o .
            }
            UNION {
                ?exp a schema:Experiment ;
                     schema:hasMetadata ?m .
                ?m ?p ?o .
            }
            UNION {
                ?exp a schema:Experiment ;
                     schema:hasData ?d .
                ?d ?p ?o .
            }
        }
    }
    """
    results = dataset.query(query)
    return sorted(set(
        get_local_name(row.p)
        for row in results if row.p and get_local_name(row.p) not in ("name", "uuid")
    ))

def get_experiments_in_graph(graph_uri, extra_preds):
    select_clause = "?experiment ?uuid ?name"
    optional_clauses = ""

    for i, pred in enumerate(extra_preds):
        if pred:
            var = f"?extra{i}"
            select_clause += f" {var}"
            optional_clauses += f"""
                OPTIONAL {{ ?experiment <http://schema.org/{pred}> {var} . }} 
                OPTIONAL {{
                    ?experiment <http://schema.org/hasData> ?data{i} .
                    ?data{i} <http://schema.org/{pred}> {var} .
                }}
                OPTIONAL {{
                    ?experiment <http://schema.org/hasMetadata> ?meta{i} .
                    ?meta{i} <http://schema.org/{pred}> {var} .
                }}
            """

    query = f"""
    PREFIX schema: <http://schema.org/>
    SELECT DISTINCT {select_clause} WHERE {{
        GRAPH <{graph_uri}> {{
            ?experiment a schema:Experiment ;
                        schema:uuid ?uuid ;
                        schema:name ?name .
            {optional_clauses}
        }}
    }}
    """
    return dataset.query(query)

##### GPT generated UI ##### Change to comodo 
# --- UI Setup ---
root = tk.Tk()
root.title("RDF Multi-Graph Query Builder")
root.geometry("800x600")

selected_subject = tk.StringVar()
selected_predicate = tk.StringVar()
selected_object = tk.StringVar()
extra_field_vars = [tk.StringVar(), tk.StringVar(), tk.StringVar()]
current_subject = None
filters = {}

# --- Subject Frame ---
frame_s = tk.Frame(root)
frame_s.pack(pady=10, fill='x')

ttk.Label(frame_s, text="Select a subject:").pack(anchor="w")
frame_s_inner = tk.Frame(frame_s)
frame_s_inner.pack(fill='x')

subjects = get_unique_subjects()
s_menu = ttk.Combobox(frame_s_inner, textvariable=selected_subject, values=subjects, state="readonly", width=40)
s_menu.pack(side="left", padx=(0,10))

def confirm_subject():
    global current_subject, filters
    subj = selected_subject.get()
    if not subj:
        return
    current_subject = subj
    filters = {subj: ("", "")}
    predicate_menu['values'] = get_predicates_for_subject(subj)
    predicate_menu.set('')
    object_menu.set('')
    object_menu['values'] = []

ttk.Button(frame_s_inner, text="Confirm Subject", command=confirm_subject).pack(side="left")

# --- Predicate Frame ---
frame_p = tk.Frame(root)
frame_p.pack(pady=10, fill='x')

ttk.Label(frame_p, text="Predicate:").pack(anchor="w")
frame_p_inner = tk.Frame(frame_p)
frame_p_inner.pack(fill='x')

predicate_menu = ttk.Combobox(frame_p_inner, textvariable=selected_predicate, state="readonly", width=40)
predicate_menu.pack(side="left", padx=(0,10))

def confirm_predicate():
    pred = selected_predicate.get()
    if not pred or not current_subject:
        return
    object_menu['values'] = get_objects_for_predicate(current_subject, pred)
    object_menu.set('')
    filters[current_subject] = (pred, "")

ttk.Button(frame_p_inner, text="Confirm Predicate", command=confirm_predicate).pack(side="left")

# --- Object Frame ---
frame_o = tk.Frame(root)
frame_o.pack(pady=10, fill='x')

ttk.Label(frame_o, text="Object:").pack(anchor="w")
frame_o_inner = tk.Frame(frame_o)
frame_o_inner.pack(fill='x')

object_menu = ttk.Combobox(frame_o_inner, textvariable=selected_object, state="readonly", width=40)
object_menu.pack(side="left", padx=(0,10))

def confirm_object():
    obj = selected_object.get()
    if not obj:
        return
    pred = selected_predicate.get()
    filters[current_subject] = (pred, obj)

ttk.Button(frame_o_inner, text="Confirm Object", command=confirm_object).pack(side="left")

# --- Extra Fields Frame ---
frame_extra = tk.Frame(root)
frame_extra.pack(pady=10, fill='x')
ttk.Label(frame_extra, text="Optional extra fields to display from Experiment/MetaData/Data:").pack(anchor="w")

extra_fields_inner = tk.Frame(frame_extra)
extra_fields_inner.pack(fill='x')

extra_predicates = [""] + get_all_experiment_related_predicates()


for i in range(3):
    menu = ttk.Combobox(extra_fields_inner, textvariable=extra_field_vars[i], values=extra_predicates, state="readonly", width=25)
    menu.pack(side="left", padx=5)

# --- Search + Output ---
def on_search():
    result_output.config(state="normal")
    result_output.delete(1.0, tk.END)

    if not all([selected_subject.get(), selected_predicate.get(), selected_object.get()]):
        result_output.insert(tk.END, " Please confirm subject, predicate, and object.")
        result_output.config(state="disabled")
        return

    matching_graphs = find_matching_graphs(filters)
    if not matching_graphs:
        result_output.insert(tk.END, " No matching graphs found.")
    else:
        selected_extra = [v.get() for v in extra_field_vars if v.get()]
        for graph_uri in matching_graphs:
            graph_name = get_local_name(graph_uri)
            experiments = get_experiments_in_graph(graph_uri, selected_extra)
            for row in experiments:
                base = f"Graph: {graph_name}, Experiment: {get_local_name(row.experiment)}, UUID: {row.uuid}, Name: {row.name}"
                extras = ""
                for i, pred in enumerate(selected_extra):
                    value = getattr(row, f"extra{i}", "")
                    if value:
                        extras += f", {pred}: {value}"
                result_output.insert(tk.END, base + extras + "\n")

    result_output.config(state="disabled")

ttk.Button(root, text="Search", command=on_search).pack(pady=10)

result_output = tk.Text(root, height=12, wrap="word", state="disabled", background="#f5f5f5")
result_output.pack(fill="both", expand=True, padx=10, pady=10)

root.mainloop()
