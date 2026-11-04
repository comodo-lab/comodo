import os
import sys

import json
from unittest.mock import MagicMock

import pytest
from dash import no_update
from dash.exceptions import PreventUpdate

# utils.influx_query reads these at import time
for var in ("INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET"):
    os.environ.setdefault(var, "test")

import src.control_window as cw
import src.heartbeats as hb
import src.saved_configs as sc
import src.spc_setup as spc

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
    """The button text, without its icon or spinner."""
    return output[0][-1].children


def icon(output):
    return output[0][0].className


class TestButtonStates:
    def test_idle_starts(self):
        out = cw.update_experiment_button(heartbeats("idle"), None)
        assert label(out) == "Start experiment"
        assert "bi-play-circle" in icon(out)
        assert out[1:] == ("success", None, False)

    def test_running_stops(self):
        out = cw.update_experiment_button(heartbeats("running", "exp-7"), None)
        assert label(out) == "Stop experiment exp-7"
        assert "bi-stop-circle" in icon(out)
        assert out[1:] == ("danger", "exp-7", False)

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
        assert label(out) == "No controller heartbeat"
        assert out[1:] == ("secondary", None, True)


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
        assert label(out) == "Start experiment"
        assert out[1:] == ("success", None, False)


class TestStartExperiment:
    SPC_ID = "s-v--a-o"
    GAINS = {"k_p": 10.0, "k_i": 1.0, "k_d": 0.1, "k_aw": 0.05, "k_df": 0.01}

    @pytest.fixture
    def publisher(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sc, "DATA_DIR", str(tmp_path))
        mock = MagicMock()
        monkeypatch.setattr(cw.MQTTPublisher, "get_instance", lambda: mock)
        return mock

    def start(self, spcs):
        meta = {"file": None, "name": "test", "saved_name": "test", "saved": None}
        return cw.start_experiment(
            [{"id": "x", "time": 0, "s/v": 1, "s/v_profile": "linear"}],
            [{"name": "s/v", "key": "tolerance", "value": 1}],
            [{"name": "resolution", "value": 2}],
            spcs,
            *[dict(meta) for _ in sc.KINDS],
        )

    def test_sends_spc_config(self, publisher, tmp_path):
        out = self.start([{"name": self.SPC_ID, **self.GAINS}])

        topic, payload = publisher.publish.call_args.args
        assert topic == "ui/start"
        experiment = json.loads(payload)
        assert experiment["config"] == {
            "resolution": 2,
            "instruments": {"s": {"v": {"tolerance": 1}}},
            "spcs": {self.SPC_ID: {"pid": {**self.GAINS, "max_rate": None}}},
        }
        # A version of each kind is saved and linked from the run, including spcs
        assert len(out) == 1 + len(sc.KINDS)
        assert out[-1]["saved"] == [{"name": self.SPC_ID, **self.GAINS}]
        assert len(list((tmp_path / "runs").iterdir())) == 1
        assert len(list((tmp_path / "spcs").iterdir())) == 1

    def test_invalid_spc_config_does_not_start(self, publisher):
        out = self.start([{"name": self.SPC_ID, **self.GAINS, "k_p": "abc"}])

        publisher.publish.assert_called_once()
        topic, payload = publisher.publish.call_args.args
        assert topic == "error/ui"
        assert json.loads(payload)["code"] == "spc_setup"
        assert out == (None, *[no_update] * len(sc.KINDS))


class TestToggleManualControl:
    def test_ignores_render(self):
        with pytest.raises(PreventUpdate):
            cw.toggle_manual_control(0, False)

    def test_opens(self):
        is_open, children, color = cw.toggle_manual_control(1, False)
        assert is_open
        assert children[-1].children == "Hide Manual Control"
        assert "bi-sliders" in children[0].className
        assert color == "warning"

    def test_closes(self):
        is_open, children, _ = cw.toggle_manual_control(2, True)
        assert not is_open
        assert children[-1].children == "Take Manual Control"


class TestManualValues:
    def store(self, stale=(), **heartbeats):
        return {
            "heartbeats": {t: {"payload": p, "received": 0} for t, p in heartbeats.items()},
            "stale": list(stale),
        }

    FURNACE = "instruments/furnace/heartbeat"
    PRESSURE = "instruments/pressure/heartbeat"
    SPC = "setpoint_controllers/pressure-pressure--mass_flow-mass_flow/heartbeat"

    def instrument(self, variable, measurement, setpoints):
        return {
            "state": {"status": "running", "measurements": {variable: measurement}},
            "setpoints": setpoints,
            "config": {},
        }

    def test_actuator(self):
        data = self.store(
            **{self.FURNACE: self.instrument("temperature", 24.5, {"temperature": 25})}
        )
        assert cw.manual_values(data, "furnace/temperature") == (24.5, 25)

    def test_spc_sensor_setpoint(self):
        data = self.store(
            **{
                self.PRESSURE: self.instrument("pressure", 1.1, {}),
                self.SPC: {
                    "config": {"sensor": "pressure/pressure", "actuator": "mass_flow/mass_flow"},
                    "setpoints": {"sensor_setpoint": 1.5},
                },
            }
        )
        assert cw.manual_values(data, "pressure/pressure") == (1.1, 1.5)

    def test_missing_or_stale(self):
        data = self.store(
            stale=[self.FURNACE],
            **{self.FURNACE: self.instrument("temperature", 24.5, {"temperature": 25})},
        )
        assert cw.manual_values(data, "furnace/temperature") == (None, None)
        assert cw.manual_values(None, "furnace/temperature") == (None, None)

    def test_update_skips_unknown_values(self):
        data = self.store(**{self.FURNACE: self.instrument("temperature", 24.5, {})})
        out = cw.update_control_component(data, {"index": "furnace/temperature"})
        assert out == (24.5, no_update)
