import json
import os
import time

import paho.mqtt.client as mqtt
import pytest

from utils.tests.mocks.mock_comodo_yaml_dict import mock_comodo_yaml_dict
from utils.tests.mocks.mock_comodo_config import mock_comodo_config
from utils.tests.mocks.mock_experiment import mock_experiment_dict

settings = {
    "MQTT_HOST": os.environ["MQTT_HOST"],
    "MQTT_USER": os.environ["MQTT_USER"],
    "MQTT_PASS": os.environ["MQTT_PASS"],
    # Timeouts, in seconds
    "HEARTBEAT_TIMEOUT": int(os.environ.get("HEARTBEAT_TIMEOUT", 20)),
    "SETPOINT_TIMEOUT": int(os.environ.get("SETPOINT_TIMEOUT", 30)),
    "EXPERIMENT_TIMEOUT": int(os.environ.get("EXPERIMENT_TIMEOUT", 120)),
    "INFLUX_TIMEOUT": int(os.environ.get("INFLUX_TIMEOUT", 30)),
    "INFLUX_URL": os.environ["INFLUX_URL"],
    "INFLUX_TOKEN": os.environ["INFLUX_TOKEN"],
    "INFLUX_ORG": os.environ["INFLUX_ORG"],
    "INFLUX_BUCKETS": os.environ["INFLUX_BUCKET"].split(","),
    "CONTROLLER_DATA": "/controller_data",
}


# ----------------- Fixtures ----------------- #


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
        "commands": [],  # controller/command/start, stop and reset, as (topic, payload)
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
        elif t in [
            "controller/command/start",
            "controller/command/stop",
            "controller/command/reset",
        ]:
            collected["commands"].append((t, json.loads(p)))

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.username_pw_set(settings["MQTT_USER"], settings["MQTT_PASS"])
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(settings["MQTT_HOST"], 1883, 60)
    c.loop_start()

    deadline = time.time() + 10
    while not collected["connected"] and time.time() < deadline:
        time.sleep(0.1)

    if not collected["connected"]:
        pytest.fail("Could not connect to MQTT broker")

    collected["c"] = c
    yield collected
    c.loop_stop()


# ----------------- Helpers ----------------- #


def wait_until(bus, condition, timeout, description, interval=0.5, allow_errors=False):
    """
    Polls condition() until it is true, printing what it is waiting for every 3s.
    The description can be a string, or a callable returning one, to report the current state.
    Unless allow_errors is set to True, it fails as soon as any error is received.
    Returns whether condition() became true before the timeout (a timeout of 0 checks it once).
    """
    deadline = time.time() + timeout
    last_report = time.time()
    while True:
        if not allow_errors and bus["errors"]:
            pytest.fail(f"Error received: {bus['errors']}")
        if condition():
            return True
        if time.time() >= deadline:
            return False
        if time.time() - last_report >= 3:
            text = description() if callable(description) else description
            print(f"  Waiting for {text}...")
            last_report = time.time()
        time.sleep(interval)


def pending_spc_pid(bus, spcs_config):
    """
    Returns the setpoint controllers that do not (yet) report the PID values in spcs_config
    ({spc_id: {"pid": {...}}}) in their heartbeat.
    """
    pending = []
    for spc_id, spc_config in spcs_config.items():
        heartbeat = bus["spc_heartbeats"].get(
            f"setpoint_controllers/{spc_id}/heartbeat"
        )
        pid = heartbeat["config"]["pid"] if heartbeat else {}
        if not all(pid.get(k) == v for k, v in spc_config["pid"].items()):
            pending.append(spc_id)
    return sorted(pending)


def with_pid(spcs_config, **gains):
    """
    Returns spcs_config with the given PID gains changed in every setpoint controller.
    """
    return {
        spc_id: {"pid": {**spc_config["pid"], **gains}}
        for spc_id, spc_config in spcs_config.items()
    }


def dump_files(experiment_id):
    """
    Returns the CSV files the controller dumps the database of an experiment to, one per bucket.
    """
    return [
        f"{settings['CONTROLLER_DATA']}/{experiment_id}/{b}.csv"
        for b in settings["INFLUX_BUCKETS"]
    ]


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


# ----------------- Pytest output ----------------- #


class EndTestNameLine:
    """
    When run-integration-tests.sh streams the logs of some services (--logs), they are printed while a test runs,
    which would continue the line pytest started with the test's name.
    So that line is ended with "Starting...", and the test's name is printed again with its result.

    This relies on how pytest's verbose terminal reporter writes each test's line:
    it only starts a new line (and writes the test's name) if the current line isn't the test's already.
    """

    def __init__(self, config):
        self.config = config
        self.prefix = (
            None  # The test's name, as pytest writes it at the start of its line
        )

    @property
    def reporter(self):
        return self.config.pluginmanager.get_plugin("terminalreporter")

    @pytest.hookimpl(trylast=True)
    def pytest_runtest_logstart(self):
        # pytest has just written the test's name: end the line
        self.prefix = self.reporter.currentfspath
        self.reporter.write("Starting...", green=True)
        self.reporter.line("")
        # Not writing to a terminal, so the output is buffered: flush it before the logs arrive
        self.reporter.flush()

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        # Write the test's name again, before pytest writes its result, so pytest doesn't add an empty line first
        _, _, word = self.config.hook.pytest_report_teststatus(
            report=report, config=self.config
        )
        if word and self.prefix:
            self.reporter.write(self.prefix)
            self.reporter.currentfspath = self.prefix
            self.prefix = None


def pytest_configure(config):
    if os.environ.get("STREAMING_LOGS"):
        config.pluginmanager.register(EndTestNameLine(config), "end_test_name_line")
