"""
Integration tests for the Firmware lifecycle.
"""

import asyncio
import json
import os

import pytest

import main, src.instrument, src.watchdog

from tests.conftest import (
    expected_config,
    firmware_env,
    wait_for_message,
    heartbeat_matches,
    measurement_matches,
)


async def fake_controller(message_bus, controller, interval):
    """
    Publishes the controller's heartbeat every `interval` seconds, with the experiment id in controller["experiment_id"],
    so the firmware's watchdog hears from a controller. Cancel the task to simulate the controller dying.
    """
    while True:
        message_bus.publish(
            "controller/heartbeat",
            json.dumps(
                {
                    "config": {"experiment_id": controller["experiment_id"]},
                    "setpoints": {},
                    "state": {"status": "idle", "variables": {}},
                }
            ),
        )
        await asyncio.sleep(interval)


@pytest.fixture
def watchdogs(monkeypatch):
    """Records the watchdogs created by the firmware, so tests can wait for them to be armed."""
    created = []

    class RecordedWatchdog(src.watchdog.FirmwareWatchdog):
        def __init__(self, istate):
            super().__init__(istate)
            created.append(self)

    monkeypatch.setattr(main.watchdog, "FirmwareWatchdog", RecordedWatchdog)
    return created


async def wait_until_armed(watchdogs, timeout=2):
    """Waits until the firmware's watchdog has heard from the controller."""
    async with asyncio.timeout(timeout):
        while not watchdogs or watchdogs[0].last_contact is None:
            await asyncio.sleep(0.01)


@pytest.fixture
def fast_firmware_env(firmware_env, monkeypatch):
    """A generic, simulated instrument with fast intervals, so the tests run quickly."""
    env = {
        **firmware_env,
        "FIRMWARE": "generic_instrument",
        "MEASUREMENT_INTERVALS": '{"temperature": 0.01, "pressure": 0.01}',
        "HEARTBEAT_INTERVAL": "0.01",
        # A 0.5s timeout: validating each controller heartbeat takes up to ~80ms under coverage
        "MAX_MISSED_HEARTBEATS": "50",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    return env


@pytest.mark.asyncio
async def test_main_with_generic_instrument(message_bus, firmware_env, monkeypatch):
    """
    This test simulates the full initialisation and operation of the firmware,
    using a generic instrument which simulates the behaviour of a real instrument.
    MQTT communication is replaced with an in-memory message bus so that external
    services are not required.
    There is no controller, so the watchdog is never armed, and the instrument doesn't safe stop.
    """
    # Use a generic, simulated instrument with fast intervals so the test runs quickly
    firmware_env = {
        **firmware_env,
        "FIRMWARE": "generic_instrument",
        "MEASUREMENT_INTERVALS": '{"temperature": 0.01, "pressure": 0.01}',
        # A 0.03s timeout, which would safe stop the instrument straight away if the watchdog was armed
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
                expected_config(firmware_env, {"experiment_id": "e-123"}),
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
                expected_config(firmware_env, {"experiment_id": "e-123"}),
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
                expected_config(firmware_env, {"experiment_id": "e-123"}),
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
                expected_config(firmware_env, {"experiment_id": "e-123"}),
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
                expected_config(firmware_env, {"experiment_id": "e-456"}),
            ),
        )
    finally:
        # Cancel the firmware task to clean up and avoid leaving it running after the test
        firmware_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await firmware_task


async def start_experiment(
    message_bus, controller, watchdogs, fast_firmware_env, experiment_id
):
    """
    Starts an experiment once the instrument awaits one, and its watchdog heard from the controller,
    and waits until it runs.
    """
    name = fast_firmware_env["INSTRUMENT_NAME"]
    default_setpoints = json.loads(fast_firmware_env["DEFAULT_SETPOINTS"])
    await wait_for_message(
        message_bus,
        f"instruments/{name}/heartbeat",
        heartbeat_matches(
            "awaiting_experiment", default_setpoints, expected_config(fast_firmware_env)
        ),
    )
    await wait_until_armed(watchdogs)
    controller["experiment_id"] = experiment_id
    message_bus.publish(
        "controller/command/start", json.dumps({"experiment_id": experiment_id})
    )
    await wait_for_message(
        message_bus,
        f"instruments/{name}/heartbeat",
        heartbeat_matches(
            "running",
            default_setpoints,
            expected_config(fast_firmware_env, {"experiment_id": experiment_id}),
        ),
    )


@pytest.mark.asyncio
async def test_safe_stop_when_controller_dies_and_reset(
    message_bus, watchdogs, fast_firmware_env
):
    """
    The controller stops sending heartbeats mid-experiment: the instrument goes to its safe stop setpoints,
    and ignores setpoints, until a reset returns it to its default setpoints.
    """
    name = fast_firmware_env["INSTRUMENT_NAME"]
    default_setpoints = json.loads(fast_firmware_env["DEFAULT_SETPOINTS"])
    safe_setpoints = {
        **default_setpoints,
        **json.loads(fast_firmware_env["SAFE_STOP_SETPOINTS"]),
    }
    controller = {"experiment_id": None}
    controller_task = asyncio.create_task(fake_controller(message_bus, controller, 0.1))
    firmware_task = asyncio.create_task(main.start_instrument())
    try:
        await start_experiment(
            message_bus, controller, watchdogs, fast_firmware_env, "e-123"
        )

        # The controller dies
        controller_task.cancel()
        await wait_for_message(
            message_bus,
            f"instruments/{name}/heartbeat",
            heartbeat_matches(
                "safe_stop", safe_setpoints, expected_config(fast_firmware_env)
            ),
            timeout=2,
        )
        await wait_for_message(
            message_bus,
            f"instruments/{name}/temperature/measurement",
            measurement_matches(safe_setpoints["temperature"]),
        )
        errors = [
            json.loads(m.payload) for m in message_bus.get_messages("error/instrument")
        ]
        assert [e["code"] for e in errors] == ["safe_stop"]

        # Setpoints are ignored during a safe stop (e.g. from a setpoint controller)
        message_bus.publish(
            f"instruments/{name}/temperature/setpoint", json.dumps({"value": 40})
        )
        await asyncio.sleep(0.1)
        await wait_for_message(
            message_bus,
            f"instruments/{name}/heartbeat",
            heartbeat_matches(
                "safe_stop", safe_setpoints, expected_config(fast_firmware_env)
            ),
            timeout=2,
        )

        # The controller comes back, and resets the instrument
        controller["experiment_id"] = None
        controller_task = asyncio.create_task(
            fake_controller(message_bus, controller, 0.1)
        )
        message_bus.publish("controller/command/reset", json.dumps({}))
        await wait_for_message(
            message_bus,
            f"instruments/{name}/heartbeat",
            heartbeat_matches(
                "awaiting_experiment",
                default_setpoints,
                expected_config(fast_firmware_env),
            ),
        )
        await wait_for_message(
            message_bus,
            f"instruments/{name}/temperature/measurement",
            measurement_matches(default_setpoints["temperature"]),
        )
    finally:
        firmware_task.cancel()
        controller_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await firmware_task


@pytest.mark.asyncio
async def test_safe_stop_when_controller_loses_the_experiment(
    message_bus, watchdogs, fast_firmware_env
):
    """
    The controller keeps sending heartbeats, but for no experiment (e.g. it was restarted mid-experiment):
    the instrument goes to its safe stop setpoints.
    """
    name = fast_firmware_env["INSTRUMENT_NAME"]
    safe_setpoints = {
        **json.loads(fast_firmware_env["DEFAULT_SETPOINTS"]),
        **json.loads(fast_firmware_env["SAFE_STOP_SETPOINTS"]),
    }
    controller = {"experiment_id": None}
    controller_task = asyncio.create_task(fake_controller(message_bus, controller, 0.1))
    firmware_task = asyncio.create_task(main.start_instrument())
    try:
        await start_experiment(
            message_bus, controller, watchdogs, fast_firmware_env, "e-123"
        )

        # The controller restarts, and its heartbeats no longer carry the experiment
        controller["experiment_id"] = None
        await wait_for_message(
            message_bus,
            f"instruments/{name}/heartbeat",
            heartbeat_matches(
                "safe_stop", safe_setpoints, expected_config(fast_firmware_env)
            ),
            timeout=2,
        )
    finally:
        firmware_task.cancel()
        controller_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await firmware_task


@pytest.mark.asyncio
async def test_controller_restart_ends_experiment_with_error(
    message_bus, watchdogs, fast_firmware_env
):
    """
    The controller restarts quickly, before the instrument safe stops, and resets it when it starts:
    the instrument ends the experiment, going to its default setpoints, and publishes an error, as the controller lost it.
    """
    name = fast_firmware_env["INSTRUMENT_NAME"]
    default_setpoints = json.loads(fast_firmware_env["DEFAULT_SETPOINTS"])
    controller = {"experiment_id": None}
    controller_task = asyncio.create_task(fake_controller(message_bus, controller, 0.1))
    firmware_task = asyncio.create_task(main.start_instrument())
    try:
        await start_experiment(
            message_bus, controller, watchdogs, fast_firmware_env, "e-123"
        )

        # The restarted controller resets the instruments, and has no experiment
        controller["experiment_id"] = None
        message_bus.publish(
            "controller/command/reset", json.dumps({"source": "controller"})
        )
        await wait_for_message(
            message_bus,
            f"instruments/{name}/heartbeat",
            heartbeat_matches(
                "awaiting_experiment",
                default_setpoints,
                expected_config(fast_firmware_env),
            ),
        )
        errors = [
            json.loads(m.payload) for m in message_bus.get_messages("error/instrument")
        ]
        assert errors == [
            {
                "code": "experiment_reset",
                "message": f"[{name}] Experiment e-123 ended by reset from controller.",
            }
        ]
    finally:
        firmware_task.cancel()
        controller_task.cancel()
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
