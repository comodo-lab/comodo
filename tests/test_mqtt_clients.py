import pytest
from unittest.mock import patch

from tests_helper import *

from mqtt_clients import *


def callback_with_error(client, msg, obj):
    raise ValueError("This is a test error")


def test_connection_error(capsys):
    with patch("mqtt_clients.connection_timeout", 1):
        try:
            tester = MQTTClient(
                id="tester",
                topics="tester/#",
                obj=None,
                broker_address="localhost",
                port=1234,
                user=None,
                password="fake",
            )
        except TimeoutError as e:
            assert "The tester client failed to connect." in str(e)

    captured = capsys.readouterr()

    # Error in console
    assert "ERROR:" in captured.out
    assert "Client 'tester' failed to connect to broker" in captured.out
    if "tester" in locals():
        assert tester.client.is_connected() == False


def test_connection_ok(capsys):
    tester = MQTTClient(
        id="tester",
        topics="tester/#",
        obj=None,
    )
    # Wait until the client is connected
    t_now = t.time()
    while not tester.client.is_connected():
        t.sleep(time_int)
        if t.time() - t_now > timeout:
            raise TimeoutError(f"The tester client failed to connect.")

    captured = capsys.readouterr()

    # Printed confirmation
    assert "Client 'tester' connected to broker" in captured.out
    assert tester.client.is_connected() == True
    assert "'tester' subscribed to 'tester/#'" in captured.out


def test_unhandled_exceptions(capmqtt, capsys):
    tester = MQTTClient(
        "tester",
        callback_with_error,
        topics="tester/#",
        obj=None,
    )
    assert tester.client.is_connected() == True
    assert tester.callback == callback_with_error
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
    assert "tests/test_mqtt_clients.py" in captured.out
    assert "function: 'callback_with_error'" in captured.out
    assert "line: 10" in captured.out
