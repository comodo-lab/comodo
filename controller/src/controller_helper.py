import json
import re
import threading
import time
import numpy as np
import influxdb_client
import os
import csv
from datetime import datetime, timezone
from types import SimpleNamespace

import src.publish_error as pub_err

# Seconds to wait before querying the database for a dump, so Telegraf has time to write everything
INFLUX_WRITE_WAIT = 2
# The measurements and setpoints of each variable, e.g. instruments/furnace/temperature/measurement
DATA_TOPIC = re.compile(r"^instruments/([^/]+/[^/]+)/(measurement|setpoint)$")


def get_env_or_secret(env_var, secret=None, default=None):
    """
    Get the value of an environment variable or from a secret file.
    If both are set, the environment variable takes precedence.
    If neither is set, return the default value.
    """
    value = os.getenv(env_var, None)
    if value is not None:
        return value
    secret_path = os.getenv(secret, None)
    if secret_path is None:
        return default
    try:
        with open(secret_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


data_path = "data"


def assign_serial_id(obj):
    """
    Assigns a serial id to the experiment, using the format: DYY-XXX,
    where YY is the last two digits of the current year, and XXX is a three digit serial.
    It then moves and renames the experiment file from tmp to to the data folder,
    and updates the cstate object accordingly.
    """
    temp_path = obj.exp_file
    current_year = str(datetime.now().year)[-2:]
    # Each experiment has a file (DYY-XXX.json), which is moved to its directory (DYY-XXX/) once it has been dumped
    experiments = [
        f for f in os.listdir(data_path) if f.endswith(".json") or "." not in f
    ]
    current_year_files = [f for f in experiments if f.startswith(f"D{current_year}-")]
    if len(current_year_files) == 0:
        serial = 1
    else:
        serials = [int(f.split("-")[1].split(".")[0]) for f in current_year_files]
        serials.sort()
        serial = serials[-1] + 1
    serial = str(serial).zfill(3)
    new_path = f"{data_path}/D{current_year}-{serial}.json"
    os.rename(temp_path, new_path)
    obj.experiment_id = f"D{current_year}-{serial}"
    obj.exp_file = new_path


def dump_database_for_experiment(obj, on_done=None):
    """
    Dumps the influx databases for the experiment elapsed time, in a background thread,
    so the controller carries on (e.g. sending its heartbeats) while it runs.
    Once done, moves the experiment's file to its directory, clears the record of the running experiment
    (see save_running_experiment, so if the controller stops before, the experiment is dumped when it starts again),
    and calls on_done, if given (even if the dump failed).
    """
    experiment = SimpleNamespace(
        experiment_id=obj.experiment_id,
        exp_file=obj.exp_file,
        experiment_start_time=obj.experiment_start_time,
    )
    tf = datetime.now()
    threading.Thread(
        target=dump_and_clear, args=(experiment, tf, on_done), daemon=True
    ).start()


def dump_and_clear(experiment, tf, on_done=None):
    try:
        time.sleep(INFLUX_WRITE_WAIT)
        dump_database(experiment, tf)
        move_experiment_file(experiment)
    finally:
        clear_running_experiment(experiment.experiment_id)
        if on_done is not None:
            on_done()


def move_experiment_file(experiment):
    """
    Moves the experiment's file (e.g. data/D26-001.json) to its directory, with its data (data/D26-001/D26-001.json).
    """
    exp_dir_path = experiment.exp_file.replace(".json", "")
    os.makedirs(exp_dir_path, exist_ok=True)
    os.replace(
        experiment.exp_file,
        os.path.join(exp_dir_path, os.path.basename(experiment.exp_file)),
    )


def write_dump_failure(exp_dir_path, t0, tf):
    """
    Writes a dump.fail file in the experiment's directory, with the start and end times of the experiment.
    """
    try:
        os.makedirs(exp_dir_path, exist_ok=True)
        with open(os.path.join(exp_dir_path, "dump.fail"), "w") as f:
            time_interval = {"t0": f"{t0.isoformat()}Z", "tf": f"{tf.isoformat()}Z"}
            json.dump(time_interval, f)
        return f"Experiment time interval recorded in dump.fail: {json.dumps(time_interval)}"
    except Exception as e:
        error = f"Failed to write dump.fail file: {e}"
        print(f"ERROR: {error}")
        return error


def dump_database(experiment, tf):
    """
    Dumps the influx databases from the start of the experiment to tf, to two files in the experiment's directory:
    - history.csv: every value stored during the experiment, in time order, to explore what happened.
    - data.csv: the measurements and setpoints of every variable, to plot them.
    """
    influx_buckets = os.getenv("INFLUX_BUCKET", "comodo").split(",")
    influx_url = f"http://{os.getenv("INFLUX_HOST", "localhost")}:8086"
    influx_org = os.getenv("INFLUX_ORG", "comodo")
    influx_token = get_env_or_secret("INFLUX_TOKEN", "INFLUX_TOKEN_FILE", None)
    if influx_token is None:
        pub_err.database_error(f"Cannot dump influx database. INFLUX_TOKEN not set.")
        return

    t0 = experiment.experiment_start_time

    try:
        # get everything from influx database
        client = influxdb_client.InfluxDBClient(
            url=influx_url,
            token=influx_token,
            org=influx_org,
        )
        query_api = client.query_api()
        exp_dir_path = experiment.exp_file.replace(".json", "")

        if not os.path.exists(exp_dir_path):
            os.makedirs(exp_dir_path)
        records = []
        for bucket in influx_buckets:
            query = f'from(bucket: "{bucket}") |> range(start: {t0.isoformat()}Z, stop: {tf.isoformat()}Z)'
            for table in query_api.query(query, org=influx_org):
                records.extend(table.records)
        write_history(records, f"{exp_dir_path}/history.csv")
        # The times are in UTC, as in the query
        write_data(records, t0.replace(tzinfo=timezone.utc), f"{exp_dir_path}/data.csv")
        print(
            f"  Influx database for experiment {experiment.experiment_id} saved at {exp_dir_path}."
        )
    except Exception as e:
        pub_err.database_error(f"Could not dump influx database: {e}")


def write_history(records, path):
    """
    Writes every record (each value of each message) in time order, as time, topic, field, value.
    """
    rows = sorted(
        (
            (r.get_time(), r.values.get("topic", ""), r.get_field(), r.get_value())
            for r in records
        ),
        # Not by value, which can be a number or a string
        key=lambda row: row[:3],
    )
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "topic", "field", "value"])
        writer.writerows(
            [t.isoformat(), topic, field, value] for t, topic, field, value in rows
        )


def write_data(records, t0, path):
    """
    Writes the measurements and setpoints of every variable, as they were recorded, in time order,
    with a column per variable (e.g. furnace/temperature) and per setpoint (e.g. furnace/temperature_setpoint).
    Values recorded at the same time share a row, unless they are of the same column.
    Columns with nothing recorded at a row's time are left empty.
    """
    points = []
    for r in records:
        match = DATA_TOPIC.match(r.values.get("topic", ""))
        if match is None or r.get_field() != "value":
            continue
        variable, kind = match.groups()
        column = variable if kind == "measurement" else f"{variable}_setpoint"
        points.append((r.get_time(), column, r.get_value()))
    points.sort(key=lambda p: p[0])
    columns = sorted(
        {column for _, column, _ in points},
        key=lambda c: (c.removesuffix("_setpoint"), c),
    )

    rows = []  # (time, {column: value})
    for t, column, value in points:
        if not rows or rows[-1][0] != t or column in rows[-1][1]:
            rows.append((t, {}))
        rows[-1][1][column] = value

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "elapsed_s"] + columns)
        writer.writerows(
            [t.isoformat(), (t - t0).total_seconds()]
            + [values.get(column, "") for column in columns]
            for t, values in rows
        )


def running_experiment_path():
    return os.path.join(data_path, "running_experiment.json")


def save_running_experiment(obj):
    """
    Records the experiment that is starting, until it ends or is stopped (see clear_running_experiment),
    so that if the controller stops mid-experiment (e.g. it crashes, or is restarted), it knows it lost it when it starts.
    """
    with open(running_experiment_path(), "w") as f:
        json.dump(
            {
                "experiment_id": obj.experiment_id,
                "exp_file": obj.exp_file,
                "start_time": obj.experiment_start_time.isoformat(),
            },
            f,
        )


def clear_running_experiment(experiment_id=None):
    """
    Removes the record of the running experiment, once it has ended or been stopped (and dumped).
    If an experiment id is given, only if the record is of that experiment,
    as another experiment may have started while it was being dumped.
    """
    path = running_experiment_path()
    try:
        if experiment_id is not None:
            with open(path) as f:
                if json.load(f).get("experiment_id") != experiment_id:
                    return
        os.remove(path)
    except (OSError, ValueError, AttributeError):
        pass


def recover_lost_experiment():
    """
    Called when the controller starts. If a previous controller stopped mid-experiment (e.g. it crashed, or was restarted),
    publishes an error, and dumps the experiment's database (in the background), as stopping it would have.
    """
    path = running_experiment_path()
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            record = json.load(f)
        lost = SimpleNamespace(
            experiment_id=record["experiment_id"],
            exp_file=record["exp_file"],
            experiment_start_time=datetime.fromisoformat(record["start_time"]),
        )
    except (OSError, ValueError, KeyError, TypeError) as e:
        pub_err.lost_experiment(f"unknown (could not read {path}: {e})")
        clear_running_experiment()
    else:
        pub_err.lost_experiment(lost.experiment_id)
        # Clears the record once dumped
        dump_database_for_experiment(lost)
