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


HEARTBEAT_TIMEOUT = int(os.environ.get("HEARTBEAT_TIMEOUT", 60))
EXPERIMENT_TIMEOUT = int(os.environ.get("EXPERIMENT_TIMEOUT", 120))


@pytest.fixture
def expected_heartbeats(mock_comodo_config):
    INSTRUMENT_TOPICS = [
        f"instruments/{ins}" for ins in mock_comodo_config.instruments.keys()
    ]
    SPC_TOPICS = [
        f"setpoint_controller/{spc}" for spc in mock_comodo_config.spcs.keys()
    ]
    return (
        ["controller/heartbeat"]
        + [f"{topic}/heartbeat" for topic in INSTRUMENT_TOPICS]
        + [f"{topic}/heartbeat" for topic in SPC_TOPICS]
    )


@pytest.fixture(scope="module")
def bus():
    collected = {"heartbeats": {}, "errors": [], "end": None, "connected": False}

    def on_connect(c, userdata, flags, reason_code, properties):
        c.subscribe("#")
        collected["connected"] = True

    def on_message(c, userdata, msg):
        t = msg.topic
        p = msg.payload.decode(errors="replace")
        if "/heartbeat" in t:
            collected["heartbeats"][t] = time.time()
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
def test_experiment_completes(bus, mock_experiment_dict):
    experiment = mock_experiment_dict

    bus["c"].publish("ui/start", json.dumps(experiment))
    print(f"  → ui/start published")

    deadline = time.time() + EXPERIMENT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        if bus["errors"]:
            pytest.fail(f"Error received: {bus['errors']}")
        if bus["end"] is not None:
            print(f"  ← controller/event/end received")
            return
        now = time.time()
        elapsed = int(now - (deadline - EXPERIMENT_TIMEOUT))
        if now - last_report >= 3:
            print(f"  waiting for controller/event/end... ({elapsed}s)")
            last_report = now
        time.sleep(0.5)
    pytest.fail("Experiment did not complete (no controller/event/end)")


@pytest.mark.order(3)
def test_no_errors(bus):
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")
