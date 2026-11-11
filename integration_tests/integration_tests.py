import csv
import json
import os
import time

import influxdb_client
import pytest

from conftest import (
    settings,
    wait_until,
    pending_spc_pid,
    with_pid,
    dump_files,
    instrument_statuses,
    all_instruments,
    errors_since,
    reported,
)


@pytest.mark.order(1)
def test_services_ready(bus, expected_heartbeats):
    """
    Waits for all expected heartbeats to be received.
    Fails if any unexpected heartbeats are received or if it times out waiting for expected heartbeats.
    """
    expected = set(expected_heartbeats)

    def missing():
        return sorted(expected - set(bus["heartbeats"]))

    def all_received():
        unexpected = set(bus["heartbeats"]) - expected
        if unexpected:
            pytest.fail(
                f"Unexpected heartbeats received."
                f"\n  Expected: {sorted(expected)}"
                f"\n  Missing: {missing()}"
                f"\n  Unexpected: {sorted(unexpected)}"
            )
        return not missing()

    assert wait_until(
        bus=bus,
        condition=all_received,
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"heartbeats: {missing()}",
    ), (
        f"Missing heartbeats."
        f"\n  Expected: {sorted(expected)}"
        f"\n  Missing: {missing()}"
    )


@pytest.mark.order(2)
def test_default_setpoints(bus, default_setpoints):
    """
    Waits for all sensors to get to their default setpoints.
    Fails if any sensor reports a setpoint outside its tolerance after a timeout.
    """

    def classify():
        """Splits the latest measurements into correct, wrong, and without a default setpoint."""
        correct, wrong, extra = {}, {}, {}
        for topic, measured in list(bus["measurement"].items()):
            # Strip instrument/instrument_name and /measurement from topic to get sensor name
            sensor = "/".join(topic.split("/")[1:-1])
            value = json.loads(measured)["value"]
            if sensor not in default_setpoints:
                extra[sensor] = value  # Unexpected sensor
            elif (
                abs(value - default_setpoints[sensor]["setpoint"])
                <= default_setpoints[sensor]["tolerance"]
            ):
                correct[sensor] = value  # At default setpoint
            else:
                wrong[sensor] = value  # Not at default setpoint
        return correct, wrong, extra

    def summary():
        correct, wrong, extra = classify()
        return (
            f"\n    OK: {sorted(correct)}"
            f"\n    Wrong: {sorted(wrong)}"
            f"\n    No default: {sorted(extra)}"
        )

    assert wait_until(
        bus=bus,
        condition=lambda: classify()[0].keys() == default_setpoints.keys(),
        timeout=settings["SETPOINT_TIMEOUT"],
        description=lambda: f"default setpoints:{summary()}",
    ), (
        f"Not all sensors at their default setpoints."
        f"\n  Expected: {sorted(default_setpoints)}"
        f"\n  Received: {summary()}"
    )


@pytest.mark.order(3)
def test_measurements_in_influx(bus, mock_comodo_config):
    """
    Checks that all expected measurements are being stored in InfluxDB.
    Fails if any are missing after a timeout.
    """
    expected_topics = {
        f"instruments/{sensor}/measurement" for sensor in mock_comodo_config.sensors
    }
    client = influxdb_client.InfluxDBClient(
        url=settings["INFLUX_URL"],
        token=settings["INFLUX_TOKEN"],
        org=settings["INFLUX_ORG"],
    )
    query_api = client.query_api()
    found = set()
    last_error = None

    def all_stored():
        nonlocal last_error
        for bucket in settings["INFLUX_BUCKETS"]:
            query = (
                f'from(bucket: "{bucket}") |> range(start: -5m)'
                f' |> filter(fn: (r) => r._field == "value")'
                f' |> keep(columns: ["topic"]) |> distinct(column: "topic")'
            )
            try:
                tables = query_api.query(query, org=settings["INFLUX_ORG"])
                found.update(r.values.get("topic") for t in tables for r in t.records)
                last_error = None
            except Exception as e:
                # InfluxDB may still be starting up
                last_error = e
        return expected_topics <= found

    try:
        stored = wait_until(
            bus=bus,
            condition=all_stored,
            timeout=settings["INFLUX_TIMEOUT"],
            description=lambda: f"measurements in InfluxDB: {sorted(expected_topics - found)}"
            f" (last error: {last_error})",
        )
    finally:
        client.close()
    assert stored, (
        f"Measurements not stored in InfluxDB."
        f"\n  Expected: {sorted(expected_topics)}"
        f"\n  Missing: {sorted(expected_topics - found)}"
        f"\n  Last error: {last_error}"
    )


@pytest.mark.order(4)
def test_spc_configured_while_idle(bus, mock_experiment_dict):
    """
    Configures the setpoint controllers with PID values different from the default.
    Fails if spc does not get configured correctly.
    """
    # Slightly different from the experiment's, so the experiment start has to change them back
    spcs_config = with_pid(mock_experiment_dict["config"]["spcs"], k_df=0.03)
    assert spcs_config, "The mock experiment has no setpoint controllers"

    for spc_id, spc_config in spcs_config.items():
        bus["c"].publish(
            f"setpoint_controllers/{spc_id}/configure", json.dumps(spc_config)
        )
    print(f"  → setpoint_controllers/+/configure published")

    assert wait_until(
        bus=bus,
        condition=lambda: not pending_spc_pid(bus, spcs_config),
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"PID values from: {pending_spc_pid(bus, spcs_config)}",
    ), f"PID values not applied by: {pending_spc_pid(bus, spcs_config)}"


@pytest.mark.order(5)
def test_experiment_completes(bus, mock_experiment_dict):
    """
    Starts the mock experiment and waits for it to complete (the controller/event/end message).
    Can fail due to spc/instrument not getting configured correctly, sensors not following the setpoints,
    or the experiment not completing in time.
    """
    experiment = mock_experiment_dict
    experiment["config"]["spcs"] = with_pid(experiment["config"]["spcs"], k_df=0.02)

    bus["c"].publish("ui/start", json.dumps(experiment))
    print(f"  → ui/start published")

    start = time.time()
    assert wait_until(
        bus=bus,
        condition=lambda: bus["end"] is not None,
        timeout=settings["EXPERIMENT_TIMEOUT"],
        description=lambda: f"controller/event/end ({int(time.time() - start)}s)",
    ), "Experiment did not complete (no controller/event/end)"
    print(f"  ← controller/event/end received")

    # The experiment's PID values replaced the ones configured while idle
    pending = pending_spc_pid(bus, experiment["config"]["spcs"])
    assert not pending, f"Experiment PID values not applied by: {pending}"


@pytest.mark.order(6)
def test_database_dump(bus, mock_comodo_config):
    """
    Checks that the controller dumped the database to CSV files after the experiment completed.
    Fails if the CSV files are not found or if they are missing measurements from any expected topic.
    """
    assert bus["end"] is not None, "The experiment did not complete"
    experiment_id = json.loads(bus["end"])["experiment_id"]
    exp_dir = f"{settings['CONTROLLER_DATA']}/{experiment_id}"
    csv_files = dump_files(experiment_id)

    # The controller dumps the database while stopping, and returns to idle once done
    assert wait_until(
        bus=bus,
        condition=lambda: all(os.path.exists(f) for f in csv_files)
        and bus["controller_status"] == "idle",
        timeout=settings["INFLUX_TIMEOUT"],
        description=lambda: f"the database dump in {exp_dir} (controller: {bus['controller_status']})",
    ), (
        f"Database not dumped for {experiment_id}, or the controller not back to idle."
        f"\n  Expected: {csv_files}"
        f"\n  Found: {sorted(os.listdir(exp_dir)) if os.path.isdir(exp_dir) else []}"
        f"\n  Controller: {bus['controller_status']}"
    )

    assert os.path.exists(f"{settings['CONTROLLER_DATA']}/{experiment_id}.json")

    expected_topics = {
        f"instruments/{sensor}/measurement" for sensor in mock_comodo_config.sensors
    } | {"controller/command/run"}
    for csv_file in csv_files:
        # Annotated CSV: each table has its own annotations (#...) and header row
        records = []
        header = None
        with open(csv_file, newline="") as f:
            for row in csv.reader(f):
                if not row or row[0].startswith("#"):
                    continue
                if row[1:3] == ["result", "table"]:
                    header = row
                elif header is not None:
                    records.append(dict(zip(header, row)))
        assert records, f"{csv_file} has no data"
        found_topics = {r.get("topic") for r in records}
        missing = expected_topics - found_topics
        assert not missing, f"{csv_file} is missing data from: {sorted(missing)}"
        run_ids = {
            r["_value"]
            for r in records
            if r.get("topic") == "controller/command/run"
            and r["_field"] == "experiment_id"
        }
        assert run_ids == {
            experiment_id
        }, f"{csv_file} has setpoints from other experiments: {sorted(run_ids)}"


@pytest.mark.order(7)
def test_no_errors(bus):
    """
    Fails if *at any point during the integration test* error messages were generated.
    """
    if bus["errors"]:
        lines = "\n".join(f"  [{t}] {p[:200]}" for t, p in bus["errors"])
        pytest.fail(f"{len(bus['errors'])} error(s):\n{lines}")


# ----------------- Fault tests ----------------- #
# These cause errors on purpose, so they run after test_no_errors, and check their own errors.


@pytest.mark.order(8)
def test_experiment_stopped_if_sensor_cannot_keep_up_with_setpoints(
    bus, mock_experiment_dict, mock_comodo_config
):
    """
    The furnace is given a setpoint it cannot reach in time (25 to 1000 takes about 30s).
    The controller should report the furnace not keeping up with the setpoints,
    stop the experiment long before its end, and dump its database.
    """
    instruments = sorted(mock_comodo_config.instruments)
    statuses = lambda: instrument_statuses(bus, instruments)
    experiment = mock_experiment_dict
    experiment["config"]["instruments"]["furnace"]["temperature"]["tolerance"] = 1e-6
    # A single step, much longer than the test waits for, so the experiment can only end by being stopped
    experiment["experiment_definition"] = [
        {"time": 0, "furnace/temperature": 1000, "pressure/pressure": 1},
        {"time": 600, "furnace/temperature": 1000, "pressure/pressure": 1},
    ]
    # Make sure stack is ready to start
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "idle",
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"the controller to be idle",
        allow_errors=True,
    ), f"The controller is not idle: {bus['controller_status']}"
    since = len(bus["errors"])
    commands = len(bus["commands"])
    bus["c"].publish("ui/start", json.dumps(experiment))
    print("  → ui/start published, with a setpoint the furnace cannot keep up with")
    sent = lambda topic: [p for t, p in bus["commands"][commands:] if t == topic]
    # The controller should stop the experiment (controller/command/stop), after reporting the furnace
    assert wait_until(
        bus=bus,
        condition=lambda: sent("controller/command/stop"),
        timeout=settings["EXPERIMENT_TIMEOUT"],
        description=lambda: f"the experiment to be stopped (controller: {bus['controller_status']})",
        allow_errors=True,
    ), f"The experiment was not stopped: {errors_since(bus, since)}"
    experiment_id = sent("controller/command/start")[-1]["experiment_id"]
    assert sent("controller/command/stop")[0] == {"experiment_id": experiment_id}
    errors = errors_since(bus, since)
    assert reported(
        errors,
        "error/controller",
        ["experiment"],
        "Instrument furnace not keeping up with setpoints.",
    ), f"The furnace not keeping up was not reported: {errors}"
    # Reported once, and nothing else
    assert len(errors) == 1, f"Unexpected errors: {errors}"
    # The data of the stopped experiment is saved, and everything goes back to idle
    csv_files = dump_files(experiment_id)
    assert wait_until(
        bus=bus,
        condition=lambda: all(os.path.exists(f) for f in csv_files),
        timeout=settings["INFLUX_TIMEOUT"],
        description=lambda: f"the database dump of {experiment_id}",
        allow_errors=True,
    ), f"Database not dumped for the stopped experiment {experiment_id}: {csv_files}"
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "idle"
        and all_instruments(bus, instruments, "awaiting_experiment"),
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"the controller to be idle (controller: {bus['controller_status']}), "
        f"and every instrument to be awaiting an experiment {statuses()}",
        allow_errors=True,
    ), f"Not back to idle: controller {bus['controller_status']}, instruments {statuses()}"


@pytest.mark.order(9)
def test_ui_reset_clears_safe_stop(bus, mock_comodo_config):
    """
    The instruments start an experiment the controller doesn't know about (as if they lost contact with it, or missed its end),
    so they safe stop, as the controller's heartbeats don't match it, while the controller stays idle.
    A reset from the UI then returns them to their defaults.
    """
    # Make sure stack is ready to start
    instruments = sorted(mock_comodo_config.instruments)
    statuses = lambda: instrument_statuses(bus, instruments)
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "idle",
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"the controller to be idle",
        allow_errors=True,
    ), f"The controller is not idle: {bus['controller_status']}"
    # Start experiment externally, controller doesn't know about it
    since = len(bus["errors"])
    bus["c"].publish(
        "controller/command/start", json.dumps({"experiment_id": "unknown"})
    )
    print("  → controller/command/start published, for an unknown experiment")
    # Instruments should safe stop, as the controller's heartbeats don't match the experiment
    assert wait_until(
        bus=bus,
        condition=lambda: all_instruments(bus, instruments, "safe_stop"),
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"every instrument to safe stop {statuses()}",
        allow_errors=True,
    ), f"Not every instrument safe stopped: {statuses()}"
    errors = errors_since(bus, since)
    for name in instruments:
        assert reported(
            errors, "error/instrument", ["safe_stop"], f"[{name}]"
        ), f"No safe stop reported by {name}: {errors}"
    # The idle controller also rejects the start
    unexpected = [
        (t, e)
        for t, e in errors
        if not reported([(t, e)], "error/instrument", ["safe_stop"], "")
        and not reported(
            [(t, e)], "error/controller", ["incompatible_controller_status"], ""
        )
    ]
    assert not unexpected, f"Unexpected errors: {unexpected}"
    # Publish a reset from the UI
    since = len(bus["errors"])
    bus["c"].publish("ui/reset", json.dumps({}))
    print("  → ui/reset published")
    assert wait_until(
        bus=bus,
        condition=lambda: all_instruments(bus, instruments, "awaiting_experiment"),
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"every instrument to be reset {statuses()}",
        allow_errors=True,
    ), f"Not every instrument was reset: {statuses()}"
    assert ("controller/command/reset", {"source": "ui"}) in bus["commands"]
    # A ui-requested reset should not publish an error from instruments or spcs
    assert not errors_since(bus, since)


@pytest.mark.order(10)
def test_controller_restart_mid_experiment(
    bus, mock_experiment_dict, mock_comodo_config
):
    """
    The controller restarts mid-experiment: an error/exception makes it exit, and Docker restarts it.
    The restarted controller reports the lost experiment, dumps its data, and resets the instruments.
    The instruments should report an error, either as a safe stop or as a reset.
    """
    # Make sure stack is ready to start
    instruments = sorted(mock_comodo_config.instruments)
    statuses = lambda: instrument_statuses(bus, instruments)
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "idle",
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"the controller to be idle",
        allow_errors=True,
    ), f"The controller is not idle: {bus['controller_status']}"
    # Start the experiment normally and wait for it to start running
    since = len(bus["errors"])
    commands = len(bus["commands"])
    bus["c"].publish("ui/start", json.dumps(mock_experiment_dict))
    print("  → ui/start published")
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "running",
        timeout=settings["EXPERIMENT_TIMEOUT"],
        description=lambda: f"the experiment to run (controller: {bus['controller_status']})",
        allow_errors=True,
    ), f"The experiment did not run: {errors_since(bus, since)}"
    starts = [
        p for t, p in bus["commands"][commands:] if t == "controller/command/start"
    ]
    experiment_id = starts[-1]["experiment_id"]
    # Publish an error/exception to make the controller exit, and wait for it to restart
    commands = len(bus["commands"])
    bus["c"].publish(
        "error/exception",
        json.dumps(
            {"code": "integration_test", "message": "Restarting the controller."}
        ),
    )
    print(f"  → error/exception published, during experiment {experiment_id}")
    assert wait_until(
        bus=bus,
        condition=lambda: ("controller/command/reset", {"source": "controller"})
        in bus["commands"][commands:],
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: "the restarted controller to reset the instruments",
        allow_errors=True,
    ), "The restarted controller did not reset the instruments"
    # The instruments should have been reset by the controller restart
    assert wait_until(
        bus=bus,
        condition=lambda: all_instruments(bus, instruments, "awaiting_experiment"),
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: f"every instrument to be reset {statuses()}",
        allow_errors=True,
    ), f"Not every instrument was reset: {statuses()}"
    # Controller should report the lost experiment, and the instruments should report a reset or safe stop
    errors = errors_since(bus, since)
    assert reported(
        errors, "error/controller", ["experiment_lost"], experiment_id
    ), f"The lost experiment {experiment_id} was not reported: {errors}"
    for name in instruments:
        assert reported(
            errors, "error/instrument", ["experiment_reset", "safe_stop"], f"[{name}]"
        ), f"No experiment reset (or safe stop) reported by {name}: {errors}"
    # The data of the lost experiment is saved, as stopping it would have
    csv_files = dump_files(experiment_id)
    assert wait_until(
        bus=bus,
        condition=lambda: all(os.path.exists(f) for f in csv_files),
        timeout=settings["INFLUX_TIMEOUT"],
        description=lambda: f"the database dump of {experiment_id}",
        allow_errors=True,
    ), f"Database not dumped for the lost experiment {experiment_id}: {csv_files}"
    assert wait_until(
        bus=bus,
        condition=lambda: bus["controller_status"] == "idle",
        timeout=settings["HEARTBEAT_TIMEOUT"],
        description=lambda: "the restarted controller to be idle",
        allow_errors=True,
    ), f"The restarted controller is not idle: {bus['controller_status']}"
