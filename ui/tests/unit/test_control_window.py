import os
import sys

import pytest
from dash.exceptions import PreventUpdate

# utils.influx_query reads these at import time
for var in ("INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET"):
    os.environ.setdefault(var, "test")

import src.control_window as cw
import src.heartbeats as hb

NOW = 1000.0


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(cw.time, "time", lambda: NOW)


def heartbeats(state, experiment_id=None, stale=False):
    return {
        "heartbeats": {
            hb.CONTROLLER_TOPIC: {
                "payload": {
                    "state": {"status": state},
                    "config": {"experiment_id": experiment_id},
                },
                "received": NOW,
            }
        },
        "stale": [hb.CONTROLLER_TOPIC] if stale else [],
    }


def label(output):
    """The button text, without the spinner if there is one."""
    children = output[0]
    return children[-1] if isinstance(children, list) else children


class TestButtonStates:
    def test_idle_starts(self):
        out = cw.update_experiment_button(heartbeats("idle"), None)
        assert out == ("Start experiment", "success", None, False)

    def test_running_stops(self):
        out = cw.update_experiment_button(heartbeats("running", "exp-7"), None)
        assert out == ("Stop experiment exp-7", "danger", "exp-7", False)

    def test_awaiting_instruments_can_stop(self):
        out = cw.update_experiment_button(
            heartbeats("awaiting_instruments", "exp-7"), None
        )
        assert out[2:] == ("exp-7", False)

    @pytest.mark.parametrize("state", ["validating", "stopping"])
    def test_transitions_busy(self, state):
        out = cw.update_experiment_button(heartbeats(state, "exp-7"), None)
        assert label(out) == f"{state.capitalize()} experiment"
        assert out[2:] == (None, True)

    def test_no_heartbeat(self):
        out = cw.update_experiment_button(heartbeats("idle", stale=True), None)
        assert out == ("No controller heartbeat", "secondary", None, True)


class TestAfterClick:
    def click(self, state, experiment_id=None, ago=1):
        return {"state": [state, experiment_id], "time": NOW - ago}

    def test_waits_while_state_unchanged(self):
        with pytest.raises(PreventUpdate):
            cw.update_experiment_button(heartbeats("idle"), self.click("idle"))

    def test_updates_when_state_changes(self):
        out = cw.update_experiment_button(heartbeats("validating"), self.click("idle"))
        assert label(out) == "Validating experiment"

    def test_gives_up_after_timeout(self):
        click = self.click("idle", ago=cw.CLICK_TIMEOUT)
        out = cw.update_experiment_button(heartbeats("idle"), click)
        assert out == ("Start experiment", "success", None, False)
