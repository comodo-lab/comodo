from dash import html
import os

# Grafana as seen from the browser
GRAFANA_URL = f"http://{os.getenv('GRAFANA_HOST', 'localhost')}:3000"
# The uid of the provisioned dashboard, in grafana/dashboards/
DASHBOARD_UID = "dd898e71-196e-48bf-bf01-022c435e7ffa"
DISPLAY_PARAMS = "?orgId=1&from=now-5m&to=now&timezone=browser&refresh=auto&kiosk=true"
# GRAFANA_DASHBOARD_URL can be used to override the default dashboard URL (including DISPLAY_PARAMS)


def get_experiment_graph():
    """
    Creates a graph to display the experimental data.
    """
    url = os.getenv("GRAFANA_DASHBOARD_URL")
    if not url:
        url = f"{GRAFANA_URL}/d/{DASHBOARD_UID}{DISPLAY_PARAMS}"

    print(f"Using Grafana URL: \n{url}")

    graph = html.Div([html.Iframe(src=url, style={"width": "100%", "height": "80vh"})])
    return graph
