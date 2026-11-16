"""
Persistence of experiment designs, instrument setups, experiment configs,
setpoint controller setups and runs.

Each kind is saved as one YAML file per version in its own folder under DATA_DIR:
    experiments/  instruments/  configs/  spcs/  runs/
Files are never overwritten: saving always creates a new file, prefixed with a
timestamp so that sorting by filename gives chronological order.
Runs link the experiment, instruments, config and spcs files used to start an experiment.
"""

import os
import re
import uuid
from datetime import datetime

import yaml

DATA_DIR = os.getenv("UI_DATA_DIR", "/ui_data")

KINDS = ("experiment", "instruments", "config", "spcs")
FOLDERS = {
    "experiment": "experiments",
    "instruments": "instruments",
    "config": "configs",
    "spcs": "spcs",
    "run": "runs",
}
DEFAULT_NAME = "default"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
_TIMESTAMP_SUFFIX = re.compile(r" \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _folder(kind):
    return os.path.join(DATA_DIR, FOLDERS[kind])


def _slug(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:50] or "unnamed"


def _new_path(kind, name, now):
    """Returns a filename for a new version of kind, unique within its folder."""
    folder = _folder(kind)
    os.makedirs(folder, exist_ok=True)
    # The filename already starts with a timestamp, so drop any in the name
    base = f"{now:%Y%m%d-%H%M%S}_{_slug(_TIMESTAMP_SUFFIX.sub('', name))}"
    filename = f"{base}.yaml"
    counter = 1
    while os.path.exists(os.path.join(folder, filename)):
        filename = f"{base}_{counter}.yaml"
        counter += 1
    return filename


def strip_ids(rows):
    """Removes the grid row ids, which are only meaningful within a browser session."""
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def to_store(kind, rows):
    """Prepares saved rows for a dcc.Store; the experiment designer needs row ids."""
    if kind == "experiment":
        return [{**row, "id": str(uuid.uuid4())} for row in rows]
    return rows


def save(kind, name, data, now=None):
    """Saves data as a new version of kind and returns its filename."""
    now = now or datetime.now()
    filename = _new_path(kind, name, now)
    record = {
        "name": name,
        "saved_at": now.strftime(TIMESTAMP_FORMAT),
        "data": strip_ids(data),
    }
    with open(os.path.join(_folder(kind), filename), "w") as f:
        yaml.safe_dump(record, f, sort_keys=False)
    return filename


def load(kind, filename):
    """Loads a saved record ({name, saved_at, data}) of kind."""
    # basename guards against paths coming from the browser escaping the folder
    with open(os.path.join(_folder(kind), os.path.basename(filename))) as f:
        return yaml.safe_load(f)


def _saved_files(kind):
    folder = _folder(kind)
    if not os.path.isdir(folder):
        return []
    return sorted((f for f in os.listdir(folder) if f.endswith(".yaml")), reverse=True)


def list_saved(kind):
    """Returns dropdown options for the saved versions of kind, newest first."""
    options = []
    for filename in _saved_files(kind):
        try:
            record = load(kind, filename)
            name = record["name"]
        except (OSError, yaml.YAMLError, KeyError, TypeError):
            continue
        label = (
            name
            if _TIMESTAMP_SUFFIX.search(name)
            else f"{name} ({record.get('saved_at')})"
        )
        options.append({"label": label, "value": filename})
    return options


def latest(kind):
    """Returns the filename of the newest readable version of kind, or None."""
    for filename in _saved_files(kind):
        try:
            record = load(kind, filename)
            if isinstance(record, dict) and "data" in record:
                return filename
        except (OSError, yaml.YAMLError):
            continue
    return None


def reconcile(kind, rows, default):
    """
    Fits saved rows to the current comodo.yaml, which may have changed since they were saved.
    Experiment rows keep only the current columns, filling missing ones from the default row.
    Instrument rows are kept, adding the default rows missing from them.
    Config and spcs keep only the current names and fields, filling missing ones from the default.
    """
    default = strip_ids(default)
    if kind == "experiment":
        template = default[0]
        fitted = [
            {key: row.get(key, value) for key, value in template.items()}
            for row in rows
        ]
        return fitted or default
    if kind == "instruments":
        saved = {(row.get("name"), row.get("key")) for row in rows}
        return rows + [
            item for item in default if (item["name"], item["key"]) not in saved
        ]
    saved = {row.get("name"): row for row in rows}
    return [
        {
            key: saved.get(item["name"], {}).get(key, value)
            for key, value in item.items()
        }
        for item in default
    ]


def make_meta(filename, record):
    """
    Metadata kept in the browser alongside each store.
    `saved` is the file content, used to tell whether the store has unsaved changes.
    """
    return {
        "file": filename,
        "name": record["name"],
        "saved_name": record["name"],
        "saved": record["data"],
    }


def initial_state(kind, default):
    """
    Returns (store data, meta) for the newest saved version of kind.
    If nothing has been saved yet, the default is saved first.
    """
    filename = latest(kind)
    if filename is None:
        filename = save(kind, DEFAULT_NAME, default)
    record = load(kind, filename)
    data = reconcile(kind, record["data"], default)
    return to_store(kind, data), make_meta(filename, record)


def is_dirty(data, meta):
    return strip_ids(data) != meta["saved"] or meta["name"] != meta["saved_name"]


def versioned_name(name, now):
    """Appends the date-time to name, replacing any previously appended one."""
    base = _TIMESTAMP_SUFFIX.sub("", name).strip() or DEFAULT_NAME
    return f"{base} {now.strftime(TIMESTAMP_FORMAT)}"


def save_if_changed(kind, data, meta, now=None):
    """
    Returns (filename, meta) of a saved version matching data, saving a new one if needed.
    A modified version that keeps its name gets the date-time appended to it.
    """
    if not is_dirty(data, meta):
        return meta["file"], meta
    now = now or datetime.now()
    name = meta["name"].strip() or DEFAULT_NAME
    if name == meta["saved_name"]:
        name = versioned_name(name, now)
    filename = save(kind, name, data, now)
    return filename, make_meta(filename, load(kind, filename))


def save_run(experiment_id, files, now=None):
    """Saves a run linking the experiment, instruments, config and spcs files it was started with."""
    now = now or datetime.now()
    filename = _new_path("run", experiment_id, now)
    record = {
        "experiment_id": experiment_id,
        "started_at": now.strftime(TIMESTAMP_FORMAT),
        **{kind: files[kind] for kind in KINDS},
    }
    with open(os.path.join(_folder("run"), filename), "w") as f:
        yaml.safe_dump(record, f, sort_keys=False)
    return filename
