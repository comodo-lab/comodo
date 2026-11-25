from dash import html
from urllib.parse import urlsplit
import flask
import os

GRAFANA_PORT = 3000
# The uid of the provisioned dashboard, in grafana/dashboards/
DASHBOARD_UID = "dd898e71-196e-48bf-bf01-022c435e7ffa"
DISPLAY_PARAMS = "?orgId=1&from=now-5m&to=now&timezone=browser&refresh=auto&kiosk=true"
# GRAFANA_DASHBOARD_URL can be used to override the default dashboard URL (including DISPLAY_PARAMS)


def get_grafana_host():
    """
    Returns the host of Grafana, as seen from the browser: GRAFANA_HOST if set (the data stack's host),
    or else the host the browser used to open the UI, as both stacks then run on the same machine.
    """
    host = os.getenv("GRAFANA_HOST")
    if host:
        return host
    if not flask.has_request_context():
        return "localhost"
    host = urlsplit(f"//{flask.request.host}").hostname or "localhost"
    # IPv6 addresses need brackets in a URL
    return f"[{host}]" if ":" in host else host


def get_experiment_graph():
    """
    Creates a graph to display the experimental data.
    Built on each request, as the default URL depends on the host the browser used to open the UI.
    """
    url = os.getenv("GRAFANA_DASHBOARD_URL")
    if not url:
        url = f"http://{get_grafana_host()}:{GRAFANA_PORT}/d/{DASHBOARD_UID}{DISPLAY_PARAMS}"

    print(f"Using Grafana URL: \n{url}")

    graph = html.Div([html.Iframe(src=url, style={"width": "100%", "height": "80vh"})])
    return graph
