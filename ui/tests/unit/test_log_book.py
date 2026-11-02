import json
import os
import sys
from collections import deque
from types import SimpleNamespace

import pytest
from dash.exceptions import PreventUpdate

import src.log_book as lb
import src.log_window as lw


@pytest.fixture(autouse=True)
def reset_log_book(monkeypatch):
    monkeypatch.setattr(lb, "_counter", 0)
    monkeypatch.setattr(lb, "_errors", 0)
    monkeypatch.setattr(lb, "_entries", deque(maxlen=lb.MAX_ENTRIES))


def receive(topic, payload, at, monkeypatch):
    monkeypatch.setattr(lb.time, "time", lambda: at)
    if not isinstance(payload, (str, bytes)):
        payload = json.dumps(payload)
    if isinstance(payload, str):
        payload = payload.encode()
    lb.on_message(None, SimpleNamespace(topic=topic, payload=payload), None)


class TestLogBook:
    def test_stores_errors_newest_first(self, monkeypatch):
        receive("error/controller", {"code": "a", "message": "first"}, 100, monkeypatch)
        receive("error/mqtt", {"code": "b", "message": "second"}, 101, monkeypatch)
        data = lb.snapshot()
        assert data["counter"] == 2
        assert data["errors"] == 2
        assert data["entries"] == [
            {
                "id": 2,
                "received": 101,
                "type": "error",
                "source": "mqtt",
                "code": "b",
                "message": "second",
            },
            {
                "id": 1,
                "received": 100,
                "type": "error",
                "source": "controller",
                "code": "a",
                "message": "first",
            },
        ]

    def test_nested_topic_keeps_full_source(self, monkeypatch):
        receive("error/a/b", {"code": "c", "message": "m"}, 100, monkeypatch)
        assert lb.snapshot()["entries"][0]["source"] == "a/b"

    def test_invalid_json_kept_as_raw_text(self, monkeypatch):
        receive("error/firmware", "not json", 100, monkeypatch)
        entry = lb.snapshot()["entries"][0]
        assert entry["code"] == "unknown"
        assert entry["message"] == "not json"

    def test_non_object_json_kept_as_raw_text(self, monkeypatch):
        receive("error/firmware", "[1, 2]", 100, monkeypatch)
        entry = lb.snapshot()["entries"][0]
        assert entry["code"] == "unknown"
        assert entry["message"] == "[1, 2]"

    def test_missing_keys(self, monkeypatch):
        receive("error/monitor", {"other": 1}, 100, monkeypatch)
        entry = lb.snapshot()["entries"][0]
        assert entry["code"] == "unknown"
        assert entry["message"] == '{"other": 1}'

    @pytest.mark.parametrize(
        "topic, payload, source, message",
        [
            (
                "ui/start",
                {"temp_id": "ab12", "config": {}},
                "ui",
                "Experiment ab12 requested.",
            ),
            (
                "controller/command/start",
                {"experiment_id": "D26-001"},
                "controller",
                "Experiment D26-001 starting.",
            ),
            (
                "controller/command/stop",
                {"experiment_id": "D26-001"},
                "controller",
                "Stopping experiment D26-001.",
            ),
        ],
    )
    def test_lifecycle_events(self, monkeypatch, topic, payload, source, message):
        receive(topic, payload, 100, monkeypatch)
        data = lb.snapshot()
        assert data["counter"] == 1
        # Events are logged, but not counted as errors
        assert data["errors"] == 0
        assert data["entries"] == [
            {
                "id": 1,
                "received": 100,
                "type": "event",
                "source": source,
                "code": topic,
                "message": message,
            }
        ]

    def test_event_with_invalid_payload(self, monkeypatch):
        receive("controller/command/stop", "not json", 100, monkeypatch)
        assert lb.snapshot()["entries"][0]["message"] == "Stopping experiment None."

    def test_subscribes_to_errors_and_events(self, monkeypatch):
        created = {}
        monkeypatch.setattr(lb, "MQTTClient", lambda **kwargs: created.update(kwargs))
        lb.start(id="ui-errors")
        assert created["topics"] == [
            "error/#",
            "ui/start",
            "controller/command/start",
            "controller/command/stop",
        ]
        assert created["callback"] == lb.on_message

    def test_drops_oldest_when_full(self, monkeypatch):
        monkeypatch.setattr(lb, "_entries", deque(maxlen=2))
        for i in range(3):
            receive("error/x", {"code": "c", "message": str(i)}, i, monkeypatch)
        data = lb.snapshot()
        assert data["counter"] == 3
        assert [e["message"] for e in data["entries"]] == ["2", "1"]


class TestLogWindow:
    def test_refresh_only_when_new_errors(self, monkeypatch):
        receive("error/controller", {"code": "a", "message": "m"}, 100, monkeypatch)
        data = lw.refresh_errors(1, None)
        assert data["counter"] == 1
        with pytest.raises(PreventUpdate):
            lw.refresh_errors(2, data)

    def test_rows_formatted(self, monkeypatch):
        receive("error/controller", {"code": "a", "message": "m"}, 0, monkeypatch)
        rows = lw.update_error_log(lb.snapshot(), "UTC")
        assert rows == [
            {
                "id": "1",
                "time": "1970-01-01 00:00:00",
                "type": "error",
                "source": "controller",
                "code": "a",
                "message": "m",
            }
        ]

    def test_no_rows_before_first_refresh(self):
        assert lw.update_error_log(None, "UTC") == []

    def test_marks_seen_only_on_log_page(self):
        # Events do not need to be seen, only errors
        data = {"counter": 5, "errors": 3, "entries": []}
        assert lw.mark_errors_seen(lw.LOG_PATH, data, 1) == 3
        with pytest.raises(PreventUpdate):
            lw.mark_errors_seen("/control", data, 1)
        with pytest.raises(PreventUpdate):
            lw.mark_errors_seen(lw.LOG_PATH, data, 3)

    def test_tab_plain_without_unseen_errors(self):
        assert lw.update_log_tab(None, None) == ("Log", {})
        data = {"counter": 5, "errors": 2, "entries": []}
        assert lw.update_log_tab(data, 2) == ("Log", {})

    def test_tab_highlighted_with_unseen_errors(self):
        assert lw.update_log_tab({"counter": 4, "errors": 1, "entries": []}, None) == (
            "Log (1 new error)",
            lw.UNSEEN_STYLE,
        )
        assert lw.update_log_tab({"counter": 5, "errors": 5, "entries": []}, 2) == (
            "Log (3 new errors)",
            lw.UNSEEN_STYLE,
        )

    def test_tab_after_ui_restart(self):
        # Seen counter from before a restart is higher than the new counter
        assert lw.update_log_tab({"counter": 2, "errors": 2, "entries": []}, 10) == (
            "Log (2 new errors)",
            lw.UNSEEN_STYLE,
        )
