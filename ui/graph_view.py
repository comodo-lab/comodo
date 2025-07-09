from dash import html
import requests

GRAFANA_URL="http://grafana:3000"

def get_dashboard_json():
    ## Get all dashboards
    response = None
    try:
        response = requests.get(f"{GRAFANA_URL}/api/search?query=&system-metrics")
        response.raise_for_status() 

        for d in response.json():
            print(f"Title: {d['title']}  UID: {d['uid']}  URL: {d['url']}")
            if d['title'] == "Comodo State Testing":
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

    comodo_dashboard = get_dashboard_json()
    if not comodo_dashboard:
        return "Sad no dashboard noises"

    url_base = f"http://localhost:3000{comodo_dashboard.get('url')}"
    url = f"{url_base}?orgId=1&from=now-5m&to=now&timezone=browser&refresh=auto&theme=light&kiosk=true"
    graph = html.Div([
        html.Iframe(src=url, style={"width": "100%", "height": "80vh"})
    ])
    return graph
