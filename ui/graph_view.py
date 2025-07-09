from dash import html


def get_experiment_graph():
    """
    Creates a graph to display the experimental data.
    """
    graph = html.Div([
        html.Iframe(src='http://localhost:3000/public-dashboards/2080316e11bc4218a203b8161073aedc', style={"width": "100%", "height": "80vh"})
    ])
    return graph
