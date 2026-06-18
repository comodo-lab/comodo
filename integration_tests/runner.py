import json
import os
import time

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASS = os.environ["MQTT_PASS"]

EXPECTED_HEARTBEATS = [
    "controller/heartbeat",
    "instruments/furnace_centre/heartbeat",
    "instruments/furnace_left/heartbeat",
    "instruments/furnace_right/heartbeat",
    "instruments/pressure_downstream/heartbeat",
    "instruments/pressure_upstream/heartbeat",
    "instruments/mass_flow/heartbeat",
    "setpoint_controller/pressure_upstream-pressure--massflow-massflow/heartbeat",
]

HEARTBEAT_TIMEOUT = int(os.environ.get("HEARTBEAT_TIMEOUT", 60))
EXPERIMENT_TIMEOUT = int(os.environ.get("EXPERIMENT_TIMEOUT", 120))


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

    bus["c"].publish("ui/start", json.dumps(experiment))
    print(f"  → ui/start published")

    deadline = time.time() + EXPERIMENT_TIMEOUT
    last_report = 0.0
    while time.time() < deadline:
        if bus["end"] is not None:
            print(f"  ← controller/event/end received")
            return
        now = time.time()
        elapsed = int(now - (deadline - EXPERIMENT_TIMEOUT))
        if now - last_report >= 10:
            print(f"  waiting for controller/event/end... ({elapsed}s)")
            last_report = now
        time.sleep(0.5)
    pytest.fail("Experiment did not complete (no controller/event/end)")


@pytest.mark.order(3)
def test_no_errors(bus):
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")
