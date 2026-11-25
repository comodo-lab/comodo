import flask
import pytest

from src import graph_view as gv

app = flask.Flask(__name__)


@pytest.fixture
def grafana_env(monkeypatch):
    monkeypatch.delenv("GRAFANA_HOST", raising=False)
    monkeypatch.delenv("GRAFANA_DASHBOARD_URL", raising=False)
    return monkeypatch


@pytest.mark.parametrize(
    "ui_host, expected",
    [
        ("10.1.2.3:8501", "10.1.2.3"),
        ("comodo-lab.local:8501", "comodo-lab.local"),
        ("localhost", "localhost"),
        ("[fe80::1]:8501", "[fe80::1]"),
    ],
)
def test_grafana_host_from_request(grafana_env, ui_host, expected):
    with app.test_request_context("/data", headers={"Host": ui_host}):
        assert gv.get_grafana_host() == expected


def test_grafana_host_from_env(grafana_env):
    grafana_env.setenv("GRAFANA_HOST", "10.9.9.9")
    with app.test_request_context("/data", headers={"Host": "10.1.2.3:8501"}):
        assert gv.get_grafana_host() == "10.9.9.9"


def test_grafana_host_without_request(grafana_env):
    assert gv.get_grafana_host() == "localhost"


def test_experiment_graph_default_url(grafana_env, capsys):
    with app.test_request_context("/data", headers={"Host": "10.1.2.3:8501"}):
        graph = gv.get_experiment_graph()

    url = graph.children[0].src
    assert url == f"http://10.1.2.3:3000/d/{gv.DASHBOARD_UID}{gv.DISPLAY_PARAMS}"
    captured = capsys.readouterr()
    assert url in captured.out


def test_experiment_graph_url_override(grafana_env):
    grafana_env.setenv("GRAFANA_DASHBOARD_URL", "http://grafana.lab:3000/d/abc")
    with app.test_request_context("/data", headers={"Host": "10.1.2.3:8501"}):
        graph = gv.get_experiment_graph()

    assert graph.children[0].src == "http://grafana.lab:3000/d/abc"
