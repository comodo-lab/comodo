import pytest
from unittest.mock import patch

from tests.tests_helper import *

from mqtt_clients import *

config = validate_file_print_errors(
    "config/config.json",
    "schemas/schema_config.json",
)
broker_address = config["mqtt"]["broker_address"]
user = config["mqtt"]["user"]
password = config["mqtt"]["password"]
connection_timeout = config["mqtt"]["connection_timeout"]


def callback_with_error(client, msg, obj):
    raise ValueError("This is a test error")


def test_connection_error(capsys):
    with pytest.raises(ConnectionRefusedError) as e:
        tester = MQTTClient(
            id="tester",
            topics="tester/#",
            obj=None,
            broker_address=broker_address,
            port=1882,
            user=user,
            password=password,
            connection_timeout=connection_timeout,
        )

    # Error in console
    if "tester" in locals():
        assert tester.client.is_connected() == False


def test_connection_timeout(capsys):
    with patch(
        "paho.mqtt.client.Client.connect",
        side_effect=lambda *args, **kwargs: t.sleep(2),
    ):
        with pytest.raises(TimeoutError) as e:
            tester = MQTTClient(
                id="tester",
                topics="tester/#",
                obj=None,
                broker_address=broker_address,
                port=1883,
                user=user,
                password=password,
                connection_timeout=1,
            )

    expected_err = "Client tester creation timed out waiting for ready"
    assert expected_err in str(e)

    # Error in console
    if "tester" in locals():
        assert tester.client.is_connected() == False


def test_connection_ok(capsys):
    tester = MQTTClient(
        id="tester",
        topics="tester/#",
        obj=None,
        broker_address=broker_address,
        port=1883,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    # Wait until the client is connected
    t_now = t.time()
    while not tester.client.is_connected():
        t.sleep(time_int)
        if t.time() - t_now > timeout:
            raise TimeoutError(f"The tester client failed to connect.")

    captured = capsys.readouterr()

    # Printed confirmation
    assert "Client tester successfully connected to broker." in captured.out
    assert tester.client.is_connected() == True


def test_unhandled_exceptions(capmqtt, capsys):
    tester = MQTTClient(
        "tester",
        callback_with_error,
        topics="tester/#",
        obj=None,
        broker_address=broker_address,
        port=1883,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    assert tester.client.is_connected() == True
    assert tester.callback == callback_with_error

    publisher = MQTTPublisher.get_instance(
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )

    capmqtt.publish(
        topic="tester/test",
        payload="test",
    )
    wait_for_message(capmqtt)

    captured = capsys.readouterr()

    # Error in mqtt
    assert capmqtt.messages[-1].topic == "ERROR/exception"
    assert "Unhandled exception in callback_with_error" in capmqtt.messages[-1].payload
    assert "This is a test error" in capmqtt.messages[-1].payload
    # Error in console
    assert "ERROR:" in captured.out
    assert "Unhandled exception in callback_with_error" in captured.out
    assert "This is a test error" in captured.out
    assert "Traceback:" in captured.out
    assert "tests/unit/test_mqtt_clients.py" in captured.out
    assert "function: 'callback_with_error'" in captured.out
