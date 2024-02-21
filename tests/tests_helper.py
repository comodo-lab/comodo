import pytest
import json
import time as t
from typing import Callable

from mqtt_clients import MQTTClient, on_client_message

time_int = 0.01  # Time interval between client connection / message checks
timeout = 3  # Client connection / message wait timeout


def valid_schema_path():
    return "schema_experiment.json"


def invalid_json_path():
    return "tests/file_fixtures/invalid_json.json"


def valid_experiment_path():
    return "tests/file_fixtures/dummy_experiment.json"


def valid_experiment_dict():
    with open(valid_experiment_path(), "r") as f:
        data = json.load(f)
    return data


def valid_experiment_dump():
    return json.dumps(valid_experiment_dict())


def invalid_experiment_path():
    return "tests/file_fixtures/invalid_experiment.json"


capmqtt_decode_utf8 = True


def make_client_fixture(client_id, callback, topics, autouse=False):
    """
    Factory to create a client fixture with connection checks and timeout.
    """

    @pytest.fixture(autouse=autouse)
    def client(state):
        # Setup before test
        c = MQTTClient(client_id, callback, topics, obj=state)
        # Wait until the client is connected
        t_now = t.time()
        while not c.client.is_connected():
            t.sleep(time_int)
            if t.time() - t_now > timeout:
                raise TimeoutError(f"The {client_id} client failed to connect.")

        yield c  # Testing happens here

        # Teardown after test
        c.client.disconnect()

    return client


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(time_int)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > timeout:
            raise TimeoutError("Timed out waiting for message")


def publish_sensor_heartbeat(capmqtt, sensor, status, setpoint):
    capmqtt.publish(
        topic="heartbeat/sensor/" + sensor["name"],
        payload=json.dumps(
            {
                "name": sensor["name"],
                "status": status,
                "setpoint": setpoint,
                "config": {k: v for k, v in sensor.items() if k != "name"},
            }
        ),
    )
