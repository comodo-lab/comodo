import json
import time as t


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


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(0.01)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > 5:
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
