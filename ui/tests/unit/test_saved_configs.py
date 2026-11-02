import os
import sys
from datetime import datetime

import pytest
import yaml

import src.saved_configs as sc

NOW = datetime(2026, 9, 25, 14, 3, 11)
LATER = datetime(2026, 9, 25, 15, 0, 0)

DEFAULT_EXPERIMENT = [{"time": 0, "a": 1, "a_profile": "linear", "id": "x"}]
DEFAULT_INSTRUMENTS = [
    {"name": "a/x", "key": "tolerance", "value": 1.0},
    {"name": "b/y", "key": "tolerance", "value": 1.0},
]


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "DATA_DIR", str(tmp_path))
    return tmp_path


class TestSaveLoad:
    def test_save_strips_ids(self):
        filename = sc.save("experiment", "test", DEFAULT_EXPERIMENT, NOW)
        record = sc.load("experiment", filename)
        assert record["name"] == "test"
        assert record["saved_at"] == "2026-09-25 14:03:11"
        assert record["data"] == [{"time": 0, "a": 1, "a_profile": "linear"}]

    def test_save_never_overwrites(self):
        first = sc.save("experiment", "test", DEFAULT_EXPERIMENT, NOW)
        second = sc.save("experiment", "test", DEFAULT_EXPERIMENT, NOW)
        assert first != second

    def test_filename_is_sanitised(self):
        filename = sc.save("experiment", "../my exp/1", DEFAULT_EXPERIMENT, NOW)
        assert filename == "20260925-140311_my_exp_1.yaml"

    def test_load_cannot_escape_folder(self, data_dir):
        (data_dir / "secret.yaml").write_text("name: secret")
        with pytest.raises(FileNotFoundError):
            sc.load("experiment", "../secret.yaml")

    def test_list_saved_newest_first(self):
        sc.save("experiment", "old", DEFAULT_EXPERIMENT, NOW)
        sc.save("experiment", "new", DEFAULT_EXPERIMENT, LATER)
        labels = [o["label"] for o in sc.list_saved("experiment")]
        assert labels == ["new (2026-09-25 15:00:00)", "old (2026-09-25 14:03:11)"]

    def test_list_saved_skips_invalid_files(self, data_dir):
        sc.save("experiment", "good", DEFAULT_EXPERIMENT, NOW)
        (data_dir / "experiments" / "99999999-bad.yaml").write_text(": : :")
        assert len(sc.list_saved("experiment")) == 1
        assert sc.latest("experiment").endswith("good.yaml")

    def test_list_saved_empty_folder(self):
        assert sc.list_saved("config") == []
        assert sc.latest("config") is None


class TestInitialState:
    def test_seeds_default_when_empty(self):
        data, meta = sc.initial_state("experiment", DEFAULT_EXPERIMENT)
        assert meta["name"] == sc.DEFAULT_NAME
        assert len(sc.list_saved("experiment")) == 1
        assert sc.strip_ids(data) == sc.strip_ids(DEFAULT_EXPERIMENT)
        assert "id" in data[0]
        assert not sc.is_dirty(data, meta)

    def test_loads_latest(self):
        sc.save("experiment", "old", DEFAULT_EXPERIMENT, NOW)
        rows = [{"time": 0, "a": 5, "a_profile": "step"}]
        latest = sc.save("experiment", "new", rows, LATER)
        data, meta = sc.initial_state("experiment", DEFAULT_EXPERIMENT)
        assert meta["file"] == latest
        assert sc.strip_ids(data) == rows


class TestReconcile:
    def test_experiment_drops_and_fills_columns(self):
        rows = [{"time": 10, "old": 3, "a_profile": "step"}]
        assert sc.reconcile("experiment", rows, DEFAULT_EXPERIMENT) == [
            {"time": 10, "a": 1, "a_profile": "step"}
        ]

    def test_experiment_empty_uses_default(self):
        assert sc.reconcile("experiment", [], DEFAULT_EXPERIMENT) == sc.strip_ids(
            DEFAULT_EXPERIMENT
        )

    def test_named_rows_follow_default_names_and_fields(self):
        rows = [
            {"name": "a", "value": 5.0, "default_setpoint": 3},
            {"name": "gone", "value": 2.0},
        ]
        default = [{"name": "a", "value": 1.0}, {"name": "b", "value": 1.0}]
        assert sc.reconcile("config", rows, default) == [
            {"name": "a", "value": 5.0},
            {"name": "b", "value": 1.0},
        ]

    def test_instrument_rows_kept_and_missing_defaults_added(self):
        rows = [
            {"name": "a", "key": "offset", "value": 273},
            {"name": "a/x", "key": "tolerance", "value": 5.0},
        ]
        assert sc.reconcile("instruments", rows, DEFAULT_INSTRUMENTS) == [
            {"name": "a", "key": "offset", "value": 273},
            {"name": "a/x", "key": "tolerance", "value": 5.0},
            {"name": "b/y", "key": "tolerance", "value": 1.0},
        ]

    def test_reconciled_changes_are_dirty(self):
        sc.save("instruments", "old", [DEFAULT_INSTRUMENTS[0]], NOW)
        data, meta = sc.initial_state("instruments", DEFAULT_INSTRUMENTS)
        assert sc.is_dirty(data, meta)


class TestSaveIfChanged:
    def setup_method(self):
        self.filename = sc.save("instruments", "setup", DEFAULT_INSTRUMENTS, NOW)
        self.meta = sc.make_meta(self.filename, sc.load("instruments", self.filename))

    def test_unchanged_reuses_file(self):
        filename, meta = sc.save_if_changed(
            "instruments", DEFAULT_INSTRUMENTS, self.meta
        )
        assert filename == self.filename
        assert meta is self.meta

    def test_modified_appends_datetime(self):
        data = [{**DEFAULT_INSTRUMENTS[0], "value": 2.0}, DEFAULT_INSTRUMENTS[1]]
        filename, meta = sc.save_if_changed("instruments", data, self.meta, LATER)
        assert filename != self.filename
        assert meta["name"] == "setup 2026-09-25 15:00:00"
        assert not sc.is_dirty(data, meta)

    def test_modified_again_replaces_datetime(self):
        meta = {**self.meta, "name": "setup 2026-09-25 14:03:11"}
        meta["saved_name"] = meta["name"]
        _, meta = sc.save_if_changed("instruments", [], meta, LATER)
        assert meta["name"] == "setup 2026-09-25 15:00:00"

    def test_renamed_keeps_new_name(self):
        meta = {**self.meta, "name": "renamed"}
        filename, meta = sc.save_if_changed(
            "instruments", DEFAULT_INSTRUMENTS, meta, LATER
        )
        assert filename != self.filename
        assert meta["name"] == "renamed"


def test_save_run_links_files(data_dir):
    files = {"experiment": "e.yaml", "instruments": "i.yaml", "config": "c.yaml"}
    filename = sc.save_run("ab12cd34", files, NOW)
    with open(data_dir / "runs" / filename) as f:
        record = yaml.safe_load(f)
    assert record == {
        "experiment_id": "ab12cd34",
        "started_at": "2026-09-25 14:03:11",
        **files,
    }
