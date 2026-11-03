import json
import os
import time

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


@pytest.fixture
def expected_heartbeats(mock_comodo_config):
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
    collected = {
        "heartbeats": {},
        "spc_heartbeats": {},
        "measurement": {},
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
        elif t.endswith("/measurement"):
            collected["measurement"][t] = p
        elif t.startswith("error/"):
            collected["errors"].append((t, p))
        elif t == "controller/event/end":
            collected["end"] = p

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


def wait_for_spc_pid(bus, spcs_config, timeout):
    """
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
    """Returns spcs_config with the given PID gains changed in every setpoint controller."""
    return {
        spc_id: {"pid": {**spc_config["pid"], **gains}}
        for spc_id, spc_config in spcs_config.items()
    }


@pytest.mark.order(3)
def test_spc_configured_while_idle(bus, mock_experiment_dict):
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


@pytest.mark.order(4)
def test_experiment_completes(bus, mock_experiment_dict):
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


@pytest.mark.order(5)
def test_no_errors(bus):
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")
