import csv
import json
import os
import time

import influxdb_client
import paho.mqtt.client as mqtt
import pytest

from utils.tests.mocks.mock_comodo_yaml_dict import mock_comodo_yaml_dict
from utils.tests.mocks.mock_comodo_config import mock_comodo_config
from utils.tests.mocks.mock_experiment import mock_experiment_dict

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASS = os.environ["MQTT_PASS"]


HEARTBEAT_TIMEOUT = int(os.environ.get("HEARTBEAT_TIMEOUT", 20))
SETPOINT_TIMEOUT = int(os.environ.get("SETPOINT_TIMEOUT", 30))
EXPERIMENT_TIMEOUT = int(os.environ.get("EXPERIMENT_TIMEOUT", 120))
INFLUX_TIMEOUT = int(os.environ.get("INFLUX_TIMEOUT", 30))

INFLUX_URL = os.environ["INFLUX_URL"]
INFLUX_TOKEN = os.environ["INFLUX_TOKEN"]
INFLUX_ORG = os.environ["INFLUX_ORG"]
INFLUX_BUCKETS = os.environ["INFLUX_BUCKET"].split(",")
CONTROLLER_DATA = "/controller_data"


@pytest.fixture
def expected_heartbeats(mock_comodo_config):
    """
    Returns a list of all expected heartbeat topics, including the controller and all instruments and setpoint controllers.
    """
    INSTRUMENT_TOPICS = [
        f"instruments/{ins}" for ins in mock_comodo_config.instruments.keys()
    ]
    SPC_TOPICS = [
        f"setpoint_controllers/{spc}" for spc in mock_comodo_config.spcs.keys()
    ]
    return (
        ["controller/heartbeat"]
        + [f"{topic}/heartbeat" for topic in INSTRUMENT_TOPICS]
        + [f"{topic}/heartbeat" for topic in SPC_TOPICS]
    )


@pytest.fixture
def default_setpoints(mock_comodo_config):
    """
    Returns a dictionary of the default setpoints for all sensors that have a default setpoint defined in the mock_comodo_config.
    """
    DEFAULT_SETPOINTS = {
        sensor_name: {
            "setpoint": sensor["default_setpoint"],
            "tolerance": sensor["tolerance"],
        }
        for sensor_name, sensor in mock_comodo_config.sensors.items()
        if "default_setpoint" in sensor
    }
    return DEFAULT_SETPOINTS


@pytest.fixture(scope="module")
def bus():
    """
    Connects to the MQTT broker and collects messages from all topics.
    Returns a dictionary with the collected messages and the MQTT client.
    """
    collected = {
        "heartbeats": {},
        "spc_heartbeats": {},
        "measurement": {},
        "controller_status": None,
        "instrument_heartbeats": {},
        "commands": [],  # controller/command/start and reset, as (topic, payload)
        "errors": [],
        "end": None,
        "connected": False,
    }

    def on_connect(c, userdata, flags, reason_code, properties):
        c.subscribe("#")
        collected["connected"] = True

    def on_message(c, userdata, msg):
        t = msg.topic
        p = msg.payload.decode(errors="replace")
        if "/heartbeat" in t:
            collected["heartbeats"][t] = time.time()
            if t.startswith("setpoint_controllers/"):
                collected["spc_heartbeats"][t] = json.loads(p)
            elif t == "controller/heartbeat":
                collected["controller_status"] = json.loads(p)["state"]["status"]
            elif t.startswith("instruments/"):
                collected["instrument_heartbeats"][t] = json.loads(p)
        elif t.endswith("/measurement"):
            collected["measurement"][t] = p
        elif t.startswith("error/"):
            collected["errors"].append((t, p))
        elif t == "controller/event/end":
            collected["end"] = p
        elif t in ["controller/command/start", "controller/command/reset"]:
            collected["commands"].append((t, json.loads(p)))

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.username_pw_set(MQTT_USER, MQTT_PASS)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_HOST, 1883, 60)
    c.loop_start()

    deadline = time.time() + 10
    while not collected["connected"] and time.time() < deadline:
        time.sleep(0.1)

    if not collected["connected"]:
        pytest.fail("Could not connect to MQTT broker")

    collected["c"] = c
    yield collected
    c.loop_stop()


@pytest.mark.order(1)
def test_services_ready(bus, expected_heartbeats):
    """
    Waits for all expected heartbeats to be received.
    Fails if any unexpected heartbeats are received or if it times out waiting for expected heartbeats.
    """
    missing_heartbeats = expected_heartbeats.copy()
    unexpected_heartbeats = []
    deadline = time.time() + HEARTBEAT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        received = set(bus["heartbeats"].keys())
        for hb_topic in received:
            if hb_topic in missing_heartbeats:
                missing_heartbeats.remove(hb_topic)
            elif hb_topic not in expected_heartbeats:
                unexpected_heartbeats += [hb_topic]
        if unexpected_heartbeats:
            pytest.fail(
                f"Unexpected heartbeats received."
                f"\n  Expected: {sorted(expected_heartbeats)}"
                f"\n  Missing: {sorted(missing_heartbeats)}"
                f"\n  Unexpected: {sorted(unexpected_heartbeats)}"
            )
        if not missing_heartbeats:
            return
        now = time.time()
        if now - last_report >= 3:
            print(f"  Waiting for heartbeats: {sorted(missing_heartbeats)}")
            last_report = now
        time.sleep(1)
    pytest.fail(
        f"Missing heartbeats."
        f"\n  Expected: {sorted(expected_heartbeats)}"
        f"\n  Missing: {sorted(missing_heartbeats)}"
    )


@pytest.mark.order(2)
def test_default_setpoints(bus, default_setpoints):
    """
    Waits for all sensors to get to their default setpoints.
    Fails if any sensor reports a setpoint outside its tolerance after a timeout.
    """
    correct_setpoints = {}
    wrong_setpoints = {}
    extra_setpoints = {}
    deadline = time.time() + SETPOINT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        for topic, measured in bus["measurement"].items():
            # Strip instrument/instrument_name and /measurement from topic to get sensor name
            sensor = "/".join(topic.split("/")[1:-1])
            measured = json.loads(measured)
            # If an expected setpoint:
            if sensor in default_setpoints:
                expected = default_setpoints[sensor]
                if (
                    abs(measured["value"] - expected["setpoint"])
                    <= expected["tolerance"]
                ):
                    correct_setpoints[sensor] = measured["value"]
                    wrong_setpoints.pop(sensor, None)
                else:
                    wrong_setpoints[sensor] = measured["value"]
                    correct_setpoints.pop(sensor, None)
            # If an unexpected setpoint:
            extra_setpoints[sensor] = measured["value"]
        if correct_setpoints.keys() == default_setpoints.keys() and not wrong_setpoints:
            return
        now = time.time()
        if now - last_report >= 3:
            print(f"  Correct setpoints: {sorted(correct_setpoints.keys())}")
            print(f"  Wrong setpoints: {sorted(wrong_setpoints.keys())}")
            print(f"  Extra setpoints: {sorted(extra_setpoints.keys())}")
            last_report = now
        time.sleep(1)
    pytest.fail(
        f"Not all sensors at their default setpoints."
        f"\n  Expected: {sorted(default_setpoints)}"
        f"\n  Received: "
        f"\n    OK: {sorted(correct_setpoints)}"
        f"\n    Wrong: {sorted(wrong_setpoints)}"
        f"\n    No default: {sorted(extra_setpoints)}"
    )


@pytest.mark.order(3)
def test_measurements_in_influx(bus, mock_comodo_config):
    """
    Checks that all expected measurements are being stored in InfluxDB.
    Fails if any are missing after a timeout.
    """
    expected_topics = {
        f"instruments/{sensor}/measurement" for sensor in mock_comodo_config.sensors
    }
    client = influxdb_client.InfluxDBClient(
        url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG
    )
    query_api = client.query_api()
    found = set()
    last_error = None
    deadline = time.time() + INFLUX_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        for bucket in INFLUX_BUCKETS:
            query = (
                f'from(bucket: "{bucket}") |> range(start: -5m)'
                f' |> filter(fn: (r) => r._field == "value")'
                f' |> keep(columns: ["topic"]) |> distinct(column: "topic")'
            )
            try:
                tables = query_api.query(query, org=INFLUX_ORG)
                found |= {r.values.get("topic") for t in tables for r in t.records}
                last_error = None
            except Exception as e:
                # InfluxDB may still be starting up
                last_error = e
        if expected_topics <= found:
            client.close()
            return
        now = time.time()
        if now - last_report >= 3:
            missing = sorted(expected_topics - found)
            print(f"  Waiting for measurements in InfluxDB: {missing}")
            if last_error is not None:
                print(f"  Last InfluxDB error: {last_error}")
            last_report = now
        time.sleep(1)
    client.close()
    pytest.fail(
        f"Measurements not stored in InfluxDB."
        f"\n  Expected: {sorted(expected_topics)}"
        f"\n  Missing: {sorted(expected_topics - found)}"
        f"\n  Last error: {last_error}"
    )


def wait_for_spc_pid(bus, spcs_config, timeout):
    """
    Helper function for test_spc_configured_while_idle and test_experiment_completes.
    Waits for every setpoint controller to report the PID values in spcs_config
    ({spc_id: {"pid": {...}}}) in its heartbeat. Returns the ones that did not.
    """
    pending = dict(spcs_config)
    deadline = time.time() + timeout
    last_report = 0.0
    while True:
        for spc_id, spc_config in list(pending.items()):
            heartbeat = bus["spc_heartbeats"].get(
                f"setpoint_controllers/{spc_id}/heartbeat"
            )
            if heartbeat is None:
                continue
            reported = heartbeat["config"]["pid"]
            if all(reported.get(k) == v for k, v in spc_config["pid"].items()):
                pending.pop(spc_id)
        now = time.time()
        if not pending or now >= deadline:
            return pending
        if now - last_report >= 3:
            print(f"  Waiting for PID values from: {sorted(pending)}")
            last_report = now
        time.sleep(0.5)


def with_pid(spcs_config, **gains):
    """
    Helper function for test_spc_configured_while_idle and test_experiment_completes.
    Returns spcs_config with the given PID gains changed in every setpoint controller.
    """
    return {
        spc_id: {"pid": {**spc_config["pid"], **gains}}
        for spc_id, spc_config in spcs_config.items()
    }


@pytest.mark.order(4)
def test_spc_configured_while_idle(bus, mock_experiment_dict):
    """
    Configures the setpoint controllers with PID values different from the default.
    Fails if spc does not get configured correctly.
    """
    # Slightly different from the experiment's, so the experiment start has to change them back
    spcs_config = with_pid(mock_experiment_dict["config"]["spcs"], k_df=0.03)
    assert spcs_config, "The mock experiment has no setpoint controllers"

    for spc_id, spc_config in spcs_config.items():
        bus["c"].publish(
            f"setpoint_controllers/{spc_id}/configure", json.dumps(spc_config)
        )
    print(f"  → setpoint_controllers/+/configure published")

    pending = wait_for_spc_pid(bus, spcs_config, HEARTBEAT_TIMEOUT)
    if pending:
        pytest.fail(f"PID values not applied by: {sorted(pending)}")


@pytest.mark.order(5)
def test_experiment_completes(bus, mock_experiment_dict):
    """
    Starts the mock experiment and waits for it to complete (the controller/event/end message).
    Can fail due to spc/instrument not getting configured correctly, sensors not following the setpoints,
    or the experiment not completing in time.
    """
    experiment = mock_experiment_dict
    experiment["config"]["spcs"] = with_pid(experiment["config"]["spcs"], k_df=0.02)

    bus["c"].publish("ui/start", json.dumps(experiment))
    print(f"  → ui/start published")

    deadline = time.time() + EXPERIMENT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        if bus["errors"]:
            pytest.fail(f"Error received: {bus['errors']}")
        if bus["end"] is not None:
            print(f"  ← controller/event/end received")
            # The experiment's PID values replaced the ones configured while idle
            pending = wait_for_spc_pid(bus, experiment["config"]["spcs"], 0)
            if pending:
                pytest.fail(f"Experiment PID values not applied by: {sorted(pending)}")
            return
        now = time.time()
        elapsed = int(now - (deadline - EXPERIMENT_TIMEOUT))
        if now - last_report >= 3:
            print(f"  waiting for controller/event/end... ({elapsed}s)")
            last_report = now
        time.sleep(0.5)
    pytest.fail("Experiment did not complete (no controller/event/end)")


@pytest.mark.order(6)
def test_database_dump(bus, mock_comodo_config):
    """
    Checks that the controller dumped the database to CSV files after the experiment completed.
    Fails if the CSV files are not found or if they are missing measurements from any expected topic.
    """
    assert bus["end"] is not None, "The experiment did not complete"
    experiment_id = json.loads(bus["end"])["experiment_id"]
    exp_dir = f"{CONTROLLER_DATA}/{experiment_id}"
    csv_files = [f"{exp_dir}/{bucket}.csv" for bucket in INFLUX_BUCKETS]

    # The controller dumps the database while stopping, and returns to idle once done
    deadline = time.time() + INFLUX_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        if bus["errors"]:
            pytest.fail(f"Error received: {bus['errors']}")
        dumped = all(os.path.exists(f) for f in csv_files)
        if dumped and bus["controller_status"] == "idle":
            break
        now = time.time()
        if now - last_report >= 3:
            print(
                f"  Waiting for the database dump in {exp_dir}..."
                f" (controller: {bus['controller_status']})"
            )
            last_report = now
        time.sleep(0.5)
    else:
        pytest.fail(
            f"Database not dumped for {experiment_id}."
            f"\n  Expected: {csv_files}"
            f"\n  Found: {sorted(os.listdir(exp_dir)) if os.path.isdir(exp_dir) else []}"
        )

    assert os.path.exists(f"{CONTROLLER_DATA}/{experiment_id}.json")

    expected_topics = {
        f"instruments/{sensor}/measurement" for sensor in mock_comodo_config.sensors
    } | {"controller/command/run"}
    for csv_file in csv_files:
        # Annotated CSV: each table has its own annotations (#...) and header row
        records = []
        header = None
        with open(csv_file, newline="") as f:
            for row in csv.reader(f):
                if not row or row[0].startswith("#"):
                    continue
                if row[1:3] == ["result", "table"]:
                    header = row
                elif header is not None:
                    records.append(dict(zip(header, row)))
        assert records, f"{csv_file} has no data"
        found_topics = {r.get("topic") for r in records}
        missing = expected_topics - found_topics
        assert not missing, f"{csv_file} is missing data from: {sorted(missing)}"
        run_ids = {
            r["_value"]
            for r in records
            if r.get("topic") == "controller/command/run"
            and r["_field"] == "experiment_id"
        }
        assert run_ids == {
            experiment_id
        }, f"{csv_file} has setpoints from other experiments: {sorted(run_ids)}"


@pytest.mark.order(7)
def test_no_errors(bus):
    """
    Fails if *at any point during the integration test* error messages were generated.
    """
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")


# ----------------- Fault tests ----------------- #
# These cause errors on purpose, so they run after test_no_errors, and check their own errors.


def wait_until(condition, timeout, description):
    """
    Waits until condition() is true, or fails after timeout seconds.
    """
    deadline = time.time() + timeout
    last_report = time.time()
    while time.time() < deadline:
        if condition():
            return
        if time.time() - last_report >= 3:
            print(f"  Waiting for {description}...")
            last_report = time.time()
        time.sleep(0.5)
    pytest.fail(f"Timed out waiting for {description}.")


def instrument_statuses(bus, instruments):
    return {
        name: bus["instrument_heartbeats"]
        .get(f"instruments/{name}/heartbeat", {})
        .get("state", {})
        .get("status")
        for name in instruments
    }


def all_instruments(bus, instruments, status):
    return all(s == status for s in instrument_statuses(bus, instruments).values())


def errors_since(bus, index):
    """The errors received since bus["errors"] had index items, as (topic, payload) with the payload decoded."""
    errors = []
    for topic, payload in bus["errors"][index:]:
        try:
            errors.append((topic, json.loads(payload)))
        except json.JSONDecodeError:
            errors.append((topic, {"message": payload}))
    return errors


def reported(errors, topic, codes, text):
    """Whether an error on topic, with one of the codes, mentions text."""
    return any(
        t == topic and e.get("code") in codes and text in e.get("message", "")
        for t, e in errors
    )


@pytest.mark.order(8)
def test_ui_reset_clears_safe_stop(bus, mock_comodo_config):
    """
    The instruments start an experiment the controller doesn't know about (as if they lost contact with it, or missed its end),
    so they safe stop, as the controller's heartbeats don't match it, while the controller stays idle.
    A reset from the UI then returns them to their defaults.
    """
    # Make sure stack is ready to start
    instruments = sorted(mock_comodo_config.instruments)
    wait_until(
        lambda: bus["controller_status"] == "idle",
        HEARTBEAT_TIMEOUT,
        "the controller to be idle",
    )
    # Start experiment externally, controller doesn't know about it
    since = len(bus["errors"])
    bus["c"].publish(
        "controller/command/start", json.dumps({"experiment_id": "unknown"})
    )
    print("  → controller/command/start published, for an unknown experiment")
    # Instruments should safe stop, as the controller's heartbeats don't match the experiment
    wait_until(
        lambda: all_instruments(bus, instruments, "safe_stop"),
        HEARTBEAT_TIMEOUT,
        f"every instrument to safe stop ({instrument_statuses(bus, instruments)})",
    )
    errors = errors_since(bus, since)
    for name in instruments:
        assert reported(
            errors, "error/instrument", ["safe_stop"], f"[{name}]"
        ), f"No safe stop reported by {name}: {errors}"
    # The idle controller also rejects the start
    unexpected = [
        (t, e)
        for t, e in errors
        if not reported([(t, e)], "error/instrument", ["safe_stop"], "")
        and not reported(
            [(t, e)], "error/controller", ["incompatible_controller_status"], ""
        )
    ]
    assert not unexpected, f"Unexpected errors: {unexpected}"
    # Publish a reset from the UI
    since = len(bus["errors"])
    bus["c"].publish("ui/reset", json.dumps({}))
    print("  → ui/reset published")
    wait_until(
        lambda: all_instruments(bus, instruments, "awaiting_experiment"),
        HEARTBEAT_TIMEOUT,
        f"every instrument to be reset ({instrument_statuses(bus, instruments)})",
    )
    assert ("controller/command/reset", {"source": "ui"}) in bus["commands"]
    # A ui-requested reset should not publish an error from instruments or spcs
    assert not errors_since(bus, since)


@pytest.mark.order(9)
def test_controller_restart_mid_experiment(
    bus, mock_experiment_dict, mock_comodo_config
):
    """
    The controller restarts mid-experiment: an error/exception makes it exit, and Docker restarts it.
    The restarted controller reports the lost experiment, dumps its data, and resets the instruments.
    The instruments should report an error, either as a safe stop or as a reset.
    """
    # Make sure stack is ready to start
    instruments = sorted(mock_comodo_config.instruments)
    wait_until(
        lambda: bus["controller_status"] == "idle",
        HEARTBEAT_TIMEOUT,
        "the controller to be idle",
    )
    # Start the experiment normally and wait for it to start running
    since = len(bus["errors"])
    commands = len(bus["commands"])
    bus["c"].publish("ui/start", json.dumps(mock_experiment_dict))
    print("  → ui/start published")
    wait_until(
        lambda: bus["controller_status"] == "running",
        EXPERIMENT_TIMEOUT,
        "the experiment to run",
    )
    starts = [
        p for t, p in bus["commands"][commands:] if t == "controller/command/start"
    ]
    experiment_id = starts[-1]["experiment_id"]
    # Publish an error/exception to make the controller exit, and wait for it to restart
    commands = len(bus["commands"])
    bus["c"].publish(
        "error/exception",
        json.dumps(
            {"code": "integration_test", "message": "Restarting the controller."}
        ),
    )
    print(f"  → error/exception published, during experiment {experiment_id}")
    wait_until(
        lambda: ("controller/command/reset", {"source": "controller"})
        in bus["commands"][commands:],
        HEARTBEAT_TIMEOUT,
        "the restarted controller to reset the instruments",
    )
    # The instruments should have been reset by the controller restart
    wait_until(
        lambda: all_instruments(bus, instruments, "awaiting_experiment"),
        HEARTBEAT_TIMEOUT,
        f"every instrument to be reset ({instrument_statuses(bus, instruments)})",
    )
    # Controller should report the lost experiment, and the instruments should report a reset or safe stop
    errors = errors_since(bus, since)
    assert reported(
        errors, "error/controller", ["experiment_lost"], experiment_id
    ), f"The lost experiment {experiment_id} was not reported: {errors}"
    for name in instruments:
        assert reported(
            errors, "error/instrument", ["experiment_reset", "safe_stop"], f"[{name}]"
        ), f"No experiment reset (or safe stop) reported by {name}: {errors}"
    # The data of the lost experiment is saved, as stopping it would have
    csv_files = [f"{CONTROLLER_DATA}/{experiment_id}/{b}.csv" for b in INFLUX_BUCKETS]
    wait_until(
        lambda: all(os.path.exists(f) for f in csv_files),
        INFLUX_TIMEOUT,
        f"the database dump of {experiment_id}",
    )
    wait_until(
        lambda: bus["controller_status"] == "idle",
        HEARTBEAT_TIMEOUT,
        "the restarted controller to be idle",
    )
