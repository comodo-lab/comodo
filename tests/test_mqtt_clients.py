import pytest

from mqtt_clients import *
from tests_helper import *


def callback_with_error(client, msg, obj):
    raise ValueError("This is a test error")


def test_unhandled_exceptions(capmqtt, capsys):
    tester = MQTTClient("tester", callback_with_error, topics="tester/#", obj=None)
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
    assert "file: 'tests/test_mqtt_clients.py'" in captured.out
    assert "function: 'callback_with_error'" in captured.out
    assert "line: 8" in captured.out
