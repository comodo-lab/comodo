"""Shared pytest fixtures and utilities for firmware tests."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from utils.tests.mocks.mock_mqtt_clients import (
    InMemoryMessageBus,
    MockMessage,
    message_bus,
    mqtt_mocks,
    parse_message_args,
    pytest_runtest_makereport,
)
from utils.tests.mocks.mock_mqtt_validator import mqtt_validator_mocks


@pytest.fixture
def firmware_env():
    return {
        "MQTT_HOST": "mqtt_host",
        "MQTT_USER": "mqtt_user",
        "MQTT_PASS": "mqtt_pass",
        "INSTRUMENT_NAME": "test_instrument",
        "FIRMWARE": "generic_instrument",
        "ADDRESS": "1.2.3.4",
        "SIMULATE": "True",
        "ACTIVE_VARIABLES": '["temperature","pressure"]',
        "DEFAULT_SETPOINTS": '{"temperature": 25, "pressure": 1.0}',
        "SAFE_STOP_SETPOINTS": '{"temperature": 0}',
        "MEASUREMENT_INTERVALS": '{"temperature": 1, "pressure": 1}',
        "HEARTBEAT_INTERVAL": 1.0,
    }


def expected_config(firmware_env, experiment=None):
    """
    Returns the expected config dictionary after loading the environment variables.

    firmware_env values are raw (JSON-encoded) environment variable strings, so they are
    parsed here the same way config.load_config() parses them, to match the real types.
    """
    if experiment is None:
        experiment = {"id": None}
    printable_config = {
        "name": firmware_env["INSTRUMENT_NAME"],
        "firmware": firmware_env["FIRMWARE"],
        "address": firmware_env["ADDRESS"],
        "simulate": str(firmware_env["SIMULATE"]).lower() in ["true", "1", "yes"],
        "variables": json.loads(firmware_env["ACTIVE_VARIABLES"]),
        "default_setpoints": json.loads(firmware_env["DEFAULT_SETPOINTS"]),
        "safe_stop_setpoints": json.loads(firmware_env["SAFE_STOP_SETPOINTS"]),
        "measurement_intervals": json.loads(firmware_env["MEASUREMENT_INTERVALS"]),
        "heartbeat_interval": float(firmware_env["HEARTBEAT_INTERVAL"]),
        "experiment": experiment,
    }
    return printable_config


async def wait_for_message(
    message_bus, topic, predicate=lambda _message: None, timeout=1
):
    """
    Wait for a bus message on `topic` that matches `predicate`.

    `predicate` should return None when a message matches, or a short string describing
    the mismatch otherwise. On timeout, that description (or the lack of any message at
    all) is raised as an AssertionError so failures are self-explanatory.
    """
    last_mismatch = f"no message was ever received on topic '{topic}'"
    try:
        async with asyncio.timeout(timeout):
            while True:
                messages = message_bus.get_messages(topic)
                if messages:
                    last_mismatch = predicate(messages[-1])
                    if last_mismatch is None:
                        return
                await asyncio.sleep(0.01)
    except TimeoutError as e:
        raise AssertionError(
            f"Timed out after {timeout}s waiting for a message on '{topic}': {last_mismatch}"
        ) from e


def heartbeat_matches(expected_state, expected_setpoints, hb_config):
    def matches(message):
        heartbeat = json.loads(message.payload)
        if heartbeat["state"] != expected_state:
            return (
                f"Wrong heartbeat: state mismatch. "
                f"-- Received: {heartbeat['state']!r}. "
                f"-- Expected {expected_state!r}"
            )
        if heartbeat["setpoints"] != expected_setpoints:
            return (
                f"Wrong heartbeat: setpoints mismatch. "
                f"-- Received: {heartbeat['setpoints']!r}. "
                f"-- Expected {expected_setpoints!r}"
            )
        if heartbeat["config"] != hb_config:
            return (
                f"Wrong heartbeat: config mismatch. "
                f"-- Received: {heartbeat['config']!r}. "
                f"-- Expected {hb_config!r}"
            )
        return None

    return matches


TOLERANCE = 0.1  # Tolerance for floating point comparisons in measurements


def measurement_matches(expected_value):
    def matches(message):
        measurement = json.loads(message.payload)
        if abs(measurement["value"] - expected_value) >= TOLERANCE:
            return (
                f"Wrong measurement: value received not within {TOLERANCE} of expected. "
                f"-- Received: {measurement['value']!r}. "
                f"-- Expected {expected_value!r}"
            )
        return None

    return matches
