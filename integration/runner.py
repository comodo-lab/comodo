import json
import os
import time

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASS = os.environ["MQTT_PASS"]

EXPECTED_HEARTBEATS = [
    "heartbeat/controller",
    "heartbeat/instrument/furnace",
    "heartbeat/instrument/furnace_left",
    "heartbeat/instrument/furnace_right",
    "heartbeat/instrument/pressure_downstream",
    "heartbeat/instrument/pressure_upstream",
    "heartbeat/instrument/massflow",
    "heartbeat/pid/pressure_upstream/pressure__massflow/massflow",
]

HEARTBEAT_TIMEOUT = 60
EXPERIMENT_TIMEOUT = 120


@pytest.fixture(scope="module")
def bus():
    collected = {"heartbeats": {}, "errors": [], "end": None, "connected": False}

    def on_connect(c, userdata, flags, rc):
        c.subscribe("#")
        collected["connected"] = True

    def on_message(c, userdata, msg):
        t = msg.topic
        p = msg.payload.decode(errors="replace")
        if t.startswith("heartbeat/"):
            collected["heartbeats"][t] = time.time()
        elif t.startswith("error/"):
            collected["errors"].append((t, p))
        elif t == "controller/end":
            collected["end"] = p

    c = mqtt.Client()
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

    yield collected
    c.loop_stop()


@pytest.mark.order(1)
def test_services_ready(bus):
    deadline = time.time() + HEARTBEAT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        received = set(bus["heartbeats"].keys())
        missing = set(EXPECTED_HEARTBEATS) - received
        if not missing:
            return
        now = time.time()
        if now - last_report >= 5:
            print(f"  heartbeats: {len(received)}/{len(EXPECTED_HEARTBEATS)} — missing: {sorted(missing)}")
            last_report = now
        time.sleep(1)
    pytest.fail(f"Missing heartbeats: {missing}")


@pytest.mark.order(2)
def test_experiment_completes(bus):
    with open("/app/experiment.json") as f:
        experiment = json.load(f)

    c = mqtt.Client()
    c.username_pw_set(MQTT_USER, MQTT_PASS)
    c.connect(MQTT_HOST, 1883, 10)
    c.publish("ui/start", json.dumps(experiment))
    c.disconnect()
    print(f"  → ui/start published")

    deadline = time.time() + EXPERIMENT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        if bus["end"] is not None:
            print(f"  ← controller/end received")
            return
        now = time.time()
        elapsed = int(now - (deadline - EXPERIMENT_TIMEOUT))
        if now - last_report >= 10:
            print(f"  waiting for controller/end... ({elapsed}s)")
            last_report = now
        time.sleep(0.5)
    pytest.fail("Experiment did not complete (no controller/end)")


@pytest.mark.order(3)
def test_no_errors(bus):
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")
