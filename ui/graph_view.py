from dash import html
import requests
import os

BACKEND_GRAFANA_URL = f"http://{os.getenv('GRAFANA_HOST', 'grafana')}:3000"
QUERY_PATH = "/api/search"
QUERY_PARAMS = "?query=&system-metrics"

DISPLAY_PARAMS = "?orgId=1&from=now-5m&to=now&timezone=browser&refresh=auto&kiosk=true"
# GRAFANA_DASHBOARD_URL can be used to override the default dashboard URL (including DISPLAY_PARAMS)


def get_dashboard_json():
    ## Get all dashboards
    response = None
    try:
        response = requests.get(f"{BACKEND_GRAFANA_URL}{QUERY_PATH}{QUERY_PARAMS}")
        response.raise_for_status()

        for d in response.json():
            print(f"Title: {d['title']}  UID: {d['uid']}  URL: {d['url']}")
            if d["title"] == "Comodo State Testing":
                return d

        # Not found
        return False
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e} - {response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False


def get_experiment_graph():
    """
    Creates a graph to display the experimental data.
    """
    url = os.getenv("GRAFANA_DASHBOARD_URL")
    if not url:
        comodo_dashboard = get_dashboard_json()
        if not comodo_dashboard:
            return "Sad no dashboard noises"
        url = f"{BACKEND_GRAFANA_URL}{comodo_dashboard.get('url')}{DISPLAY_PARAMS}"

    print(f"Using Grafana URL: \n{url}")

    graph = html.Div([html.Iframe(src=url, style={"width": "100%", "height": "80vh"})])
    return graph
