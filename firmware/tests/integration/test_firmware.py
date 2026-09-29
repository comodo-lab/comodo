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


@pytest.mark.asyncio
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
    firmware_task = asyncio.create_task(main.start_instrument())
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
        message_bus.publish(
            "controller/command/start", json.dumps({"experiment_id": "e-123"})
        )
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
        message_bus.publish(
            "controller/command/start", json.dumps({"experiment_id": "e-456"})
        )
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


def discover_instrument_plugins():
    """
    Returns the '<package>.<module>' plugin name for every instrument implementation
    file found under src/instruments (e.g. "bronkhorst.el_flow_select").
    """
    instruments_dir = os.path.join(os.path.dirname(__file__), "../../src/instruments")
    plugins = []
    for package_name in sorted(os.listdir(instruments_dir)):
        package_dir = os.path.join(instruments_dir, package_name)
        if not os.path.isdir(package_dir) or package_name.startswith("__"):
            continue
        for filename in sorted(os.listdir(package_dir)):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugins.append(f"{package_name}.{filename[:-3]}")
    return plugins


@pytest.mark.parametrize("firmware_plugin", discover_instrument_plugins())
def test_create_instrument_for_all_instrument_subclasses(firmware_plugin):
    """
    Every instrument plugin under src/instruments should be instantiable in simulation
    mode. This is enough to check at least that their ABC implementation is correct.
    Also, repeated simulated measurements are requested, to ensure the simulation does not error.
    """
    config = {
        "FIRMWARE": firmware_plugin,
        "SIMULATE": True,
        "ADDRESS": "",
        "DEFAULT_SETPOINTS": {},
        "EXTERNAL_ACTUATORS": {},
    }
    instrument_instance = src.instrument.create_instrument(config)
    assert instrument_instance is not None

    # Iterate simulated measurements per variable, checking they converge towards a setpoint
    target_setpoint = 42.0
    for variable in instrument_instance.available_variables:
        instrument_instance.set_and_go_to_setpoint(variable, target_setpoint)
        previous_error = None
        max_iterations = 1000
        for _ in range(max_iterations):
            value = instrument_instance.measure_or_simulate(variable)
            if not isinstance(value, (int, float)):
                break  # non-numeric simulation (e.g. a mass spec scan); nothing to converge
            error = abs(value - target_setpoint)
            assert (
                previous_error is None or error <= previous_error
            ), f"Simulated '{variable}' measurement did not converge to setpoint in {max_iterations} iterations."
            previous_error = error
            if error < 1e-2:
                break  # converged to setpoint
        assert variable in instrument_instance.previous_measurements
        if previous_error is not None:
            assert (
                previous_error < 1e-2
            ), f"Simulated '{variable}' measurement should reach its setpoint"
