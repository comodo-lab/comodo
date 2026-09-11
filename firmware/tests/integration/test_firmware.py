"""Firmware tests.

Given a known config and instrument driver, the firmware should produce
expected heartbeats and measurements on the MQTT bus.
"""

import json
import asyncio
import pytest
import os

import main

pytestmark = pytest.mark.asyncio


async def test_firmware(message_bus, test_instrument, get_env):
    # --------------------------------------------------------------------------
    # Set up the test environment

    # Inject the environment variables for the test instrument
    for key, value in get_env.items():
        # Set the environment variable
        os.environ[key] = value

    # Set up and run the firmware
    task = asyncio.create_task(main.main())

    # Wait for startup
    await asyncio.sleep(5)

    # Send some setpoints
    message_bus.publish(
        topic="instruments/test/setpoints",
        payload=json.dumps({"temperature": 25.0, "pressure": 1010.3}),
    )

    # Wait for a few seconds to allow the firmware to process the setpoints and publish heartbeats
    await asyncio.sleep(5)

    # Kill the firmware task
    task.cancel()

    # Check the task was successful (still running at cancel time, no exceptions)
    if task.done():
        assert task.exception() is None, "Firmware task raised an exception"
    assert not task.done(), "Firmware task was not running at cancel time"

    # --------------------------------------------------------------------------
    # Begin tests

    # Test that heartbeats have been published
    heartbeats = message_bus.get_messages(topic="instruments/test/heartbeat")
    assert len(heartbeats) > 0, "No heartbeats published"

    # Test that they have the correct shape
    for hb in heartbeats:
        payload = json.loads(hb.payload)
        assert "config" in payload
        assert "state" in payload
        assert "setpoints" in payload

        assert payload["config"] == {
            "firmware": "test_instrument",
            "address": "1.2.3.4",
            "simulate": True,
            "variables": ["temperature", "pressure"],
        }, "Payload config does not match expected config"
        assert payload["state"] == "ready"

        if payload["setpoints"] != {}:  # Only check setpoints if they have been set
            assert payload["setpoints"] == {"temperature": 25.0, "pressure": 1010.3}

    # Test that measurements have been published
    measurements = message_bus.get_messages(
        topic="instruments/test/temperature/measurement"
    )
    assert len(measurements) > 0, "No temperature measurements published"

    # Test that they have the correct shape
    for m in measurements:
        payload = json.loads(m.payload)
        assert "value" in payload
        assert isinstance(payload["value"], (int, float))
