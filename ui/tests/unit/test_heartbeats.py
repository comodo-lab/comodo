import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
import heartbeats as hb
import top_matter as tm
from config_loader import UiConfig


@pytest.fixture(autouse=True)
def reset_heartbeats(monkeypatch):
    monkeypatch.setattr(hb, "_timeout", 5)
    monkeypatch.setattr(hb, "_sources", [])
    monkeypatch.setattr(hb, "_counter", 0)
    monkeypatch.setattr(hb, "_latest", {})


def receive(topic, payload, at, monkeypatch):
    monkeypatch.setattr(hb.time, "time", lambda: at)
    msg = SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())
    hb.on_heartbeat(None, msg, None)


class TestSources:
    def test_instruments_then_spcs(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid).config
        assert hb.get_sources(config) == [
            {
                "topic": "instruments/test_sensor/heartbeat",
                "label": "test_sensor",
                "kind": "instrument",
            },
            {
                "topic": "instruments/test_spc/heartbeat",
                "label": "test_spc",
                "kind": "instrument",
            },
            {
                # Matches the spc_id used by setpoint_controller.py
                "topic": "setpoint_controllers/test_sensor-value--test_spc-output/heartbeat",
                "label": "test_sensor/value → test_spc/output",
                "kind": "spc",
            },
        ]


class TestSnapshot:
    def test_stores_latest_and_counts(self, monkeypatch):
        receive("controller/heartbeat", {"state": "idle"}, 100, monkeypatch)
        receive("controller/heartbeat", {"state": "running"}, 101, monkeypatch)
        data = hb.snapshot(now=101)
        assert data["counter"] == 2
        assert data["heartbeats"]["controller/heartbeat"] == {
            "payload": {"state": "running"},
            "received": 101,
        }
        assert data["stale"] == []

    def test_invalid_json_ignored(self):
        msg = SimpleNamespace(topic="controller/heartbeat", payload=b"not json")
        hb.on_heartbeat(None, msg, None)
        assert hb.snapshot()["counter"] == 0

    def test_stale_after_timeout(self, monkeypatch):
        receive("controller/heartbeat", {"state": "idle"}, 100, monkeypatch)
        assert hb.snapshot(now=105)["stale"] == []
        assert hb.snapshot(now=105.1)["stale"] == ["controller/heartbeat"]


class TestGetStatusDisplay:
    def data(self, payload, stale=False):
        topic = "instruments/a/heartbeat"
        return topic, {
            "heartbeats": {topic: {"payload": payload, "received": 0}},
            "stale": [topic] if stale else [],
        }

    def test_known_status(self):
        topic, data = self.data({"state": {"status": "running"}})
        display = tm.get_status_display(data, topic, tm.INSTRUMENT_STATUS_LIST)
        assert display == ("Running", "success")

    def test_no_heartbeat(self):
        display = tm.get_status_display(
            {"heartbeats": {}, "stale": []}, "x", tm.INSTRUMENT_STATUS_LIST
        )
        assert display == tm.NO_HEARTBEAT

    def test_lost_heartbeat(self):
        topic, data = self.data({"state": {"status": "running"}}, stale=True)
        display = tm.get_status_display(data, topic, tm.INSTRUMENT_STATUS_LIST)
        assert display == tm.LOST_HEARTBEAT

    def test_unknown_status(self):
        topic, data = self.data({"state": {"status": "exploded"}})
        display = tm.get_status_display(data, topic, tm.INSTRUMENT_STATUS_LIST)
        assert display == ("Unknown (exploded)", "secondary")
