"""
Integration tests for the Firmware lifecycle.
"""

import asyncio
import json
import os

import pytest

import main, src.instrument

from tests.conftest import (
    expected_config,
    firmware_env,
    wait_for_message,
    heartbeat_matches,
    measurement_matches,
)

pytestmark = pytest.mark.asyncio


async def test_main_with_generic_instrument(message_bus, firmware_env, monkeypatch):
    """
    This test simulates the full initialisation and operation of the firmware,
    using a generic instrument which simulates the behaviour of a real instrument.
    MQTT communication is replaced with an in-memory message bus so that external
    services are not required.
    """
    # Use a generic, simulated instrument with fast intervals so the test runs quickly
    firmware_env = {
        **firmware_env,
        "FIRMWARE": "generic_instrument",
        "MEASUREMENT_INTERVALS": '{"temperature": 0.01, "pressure": 0.01}',
        "HEARTBEAT_INTERVAL": "0.01",
    }
    for key, value in firmware_env.items():
        monkeypatch.setenv(key, str(value))
    assert firmware_env["ACTIVE_VARIABLES"] == '["temperature","pressure"]'

    instrument_name = firmware_env["INSTRUMENT_NAME"]
    default_setpoints = json.loads(firmware_env["DEFAULT_SETPOINTS"])
    heartbeat_topic = f"instruments/{instrument_name}/heartbeat"

    # Check generic instrument state gets created and initialised ok
    firmware_task = asyncio.create_task(main.main())
    try:
        # Check measurement ticks and heartbeat ticks are running
        await wait_for_message(
            message_bus, f"instruments/{instrument_name}/temperature/measurement"
        )
        await wait_for_message(
            message_bus, f"instruments/{instrument_name}/pressure/measurement"
        )

        # Check that the instrument state is awaiting experiment and that the default setpoints are set
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "awaiting_experiment",
                default_setpoints,
                expected_config(firmware_env),
            ),
        )
        # Check that sensors moved to the default setpoints
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/temperature/measurement",
            measurement_matches(default_setpoints["temperature"]),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/pressure/measurement",
            measurement_matches(default_setpoints["pressure"]),
        )

        # Send a start command to the instrument and check that it goes to running
        message_bus.publish("controller/command/start", json.dumps({"id": "e-123"}))
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "running",
                default_setpoints,
                expected_config(firmware_env, {"id": "e-123"}),
            ),
        )

        # Send a few new setpoints to the instrument and check that it goes to them
        message_bus.publish(
            f"instruments/{instrument_name}/temperature/setpoint",
            json.dumps({"value": 40}),
        )
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "running",
                {"temperature": 40, "pressure": default_setpoints["pressure"]},
                expected_config(firmware_env, {"id": "e-123"}),
            ),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/temperature/measurement",
            measurement_matches(40),
        )
        message_bus.publish(
            f"instruments/{instrument_name}/pressure/setpoint",
            json.dumps({"value": 2.0}),
        )
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "running",
                {"temperature": 40, "pressure": 2.0},
                expected_config(firmware_env, {"id": "e-123"}),
            ),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/pressure/measurement",
            measurement_matches(2.0),
        )

        message_bus.publish(
            f"instruments/{instrument_name}/temperature/setpoint",
            json.dumps({"value": 100}),
        )
        message_bus.publish(
            f"instruments/{instrument_name}/pressure/setpoint",
            json.dumps({"value": 0.5}),
        )
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "running",
                {"temperature": 100, "pressure": 0.5},
                expected_config(firmware_env, {"id": "e-123"}),
            ),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/temperature/measurement",
            measurement_matches(100),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/pressure/measurement",
            measurement_matches(0.5),
        )

        # Send an experiment end command to the instrument and check that it resets
        message_bus.publish("controller/event/end", json.dumps({}))
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "awaiting_experiment",
                default_setpoints,
                expected_config(firmware_env),
            ),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/temperature/measurement",
            measurement_matches(default_setpoints["temperature"]),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{instrument_name}/pressure/measurement",
            measurement_matches(default_setpoints["pressure"]),
        )

        # Check that a second experiment can be started and that the instrument goes to running again
        message_bus.publish("controller/command/start", json.dumps({"id": "e-456"}))
        await wait_for_message(
            message_bus,
            heartbeat_topic,
            heartbeat_matches(
                "running",
                default_setpoints,
                expected_config(firmware_env, {"id": "e-456"}),
            ),
        )
    finally:
        # Cancel the firmware task to clean up and avoid leaving it running after the test
        firmware_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await firmware_task
