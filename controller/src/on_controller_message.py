import functools
import json
from datetime import datetime

from utils import mqtt_clients as mqtt
from utils.interpolation import split_setpoints
from utils import mqtt_validator as mqtt_val

from src.controller_helper import (
    assign_serial_id,
    clear_running_experiment,
    dump_database_for_experiment,
    save_running_experiment,
)
import src.publish_error as pub_err
import src.validation as val


def recover_on_exception(state_callback):
    """
    Decorator for controller state callbacks. On an unhandled exception it moves the
    controller to the error state, stops the instruments if the experiment had started,
    resets it, and returns to idle, then re-raises so the generic MQTT wrapper still
    logs and publishes the error.
    """

    @functools.wraps(state_callback)
    def wrapper(client, msg, obj):
        try:
            return state_callback(client, msg, obj)
        except Exception as e:
            if getattr(e, "controller_recovered", False):
                raise
            e.controller_recovered = True
            crashed_status = obj.status
            experiment_id = obj.experiment_id
            print(
                f"Recovering controller from exception in state '{crashed_status}' during experiment '{experiment_id}'..."
            )
            # Publish stop signal if experiment had started and did not already try to stop normally.
            obj.status = "error"
            if (
                crashed_status not in ("idle", "validating", "stopping", "error")
                and experiment_id
            ):
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop",
                    json.dumps({"experiment_id": experiment_id}),
                )
            else:
                obj.reset()
                clear_running_experiment()
                client.callback = c_idle
            raise

    return wrapper


@recover_on_exception
def c_idle(client, msg, obj):
    """
    Callback for the controller when it is idle.

    It expects a "controller/command/validate" message containing a JSON object with a "file" key, which contains the path to the experiment file.

    The experiment file is then loaded, decoded, and validated against the experiment schema.

    If the experiment is valid, the experiment id is updated and the controller state and callback are updated to "starting".
    Otherwise, it resets to the idle state and publishes an error.
    """
    if msg.topic != "controller/command/validate":
        if msg.topic in ["controller/command/stop", "controller/command/reset"]:
            return
        if msg.topic.startswith("controller/command/"):
            pub_err.incompatible_controller_status(obj, msg)
        return

    # Load and decode experiment file
    try:
        # Load experiment object
        payload = mqtt_val.validate_message(msg.topic, msg.payload)

        # Set experiment file object and temp_id
        obj.exp_file = payload["file"]
        temp_id = payload["temp_id"]
        print(f"Validating experiment {temp_id}...")
    except mqtt_val.MQTTValidationException as e:
        pub_err.message_validation(e)
        return

    obj.experiment_start_time = datetime.now()
    obj.status = "validating"

    # Validate experiment configuration
    try:
        exp_config = val.validate_experiment(obj.exp_file, obj.config)

        # Compute intermediate setpoints
        obj.setpoints = split_setpoints(
            exp_config["experiment_definition"], exp_config["config"]["resolution"]
        )
        # Assign a serial experiment id
        assign_serial_id(obj)
        save_running_experiment(obj)
        m = {
            "temp_id": temp_id,
            "experiment_id": obj.experiment_id,
            "valid": True,
        }
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/validator/passed", json.dumps(m)
        )
        obj.exp_config = exp_config

        print(
            f"Experiment {temp_id} valid. Assigned experiment id: {obj.experiment_id}"
        )

        # Send live experiment config to instruments and update expected heartbeats
        instruments_config = exp_config["config"].get("instruments", {})
        for instrument_name in instruments_config:
            mqtt.MQTTPublisher.get_instance().publish(
                f"instruments/{instrument_name}/configure",
                json.dumps(instruments_config[instrument_name]),
            )
            obj.set_hb_experiment_config(
                instrument_name, instruments_config[instrument_name]
            )
        # Send live experiment config to setpoint controllers, checked in their heartbeats
        spcs_config = exp_config["config"].get("spcs", {})
        for spc_id in spcs_config:
            mqtt.MQTTPublisher.get_instance().publish(
                f"setpoint_controllers/{spc_id}/configure",
                json.dumps(spcs_config[spc_id]),
            )
        # Also expect experiment id
        for instrument_name in obj.expected_heartbeats:
            obj.set_hb_experiment_config(
                instrument_name, {"experiment_id": obj.experiment_id}
            )

        # Update state and callback of controller
        client.callback = c_starting
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/command/start",
            json.dumps({"experiment_id": obj.experiment_id}),
        )
    except (val.ExperimentValidationError, ValueError) as e:
        pub_err.experiment_validation_error(e, temp_id)
        obj.experiment_id = None
        obj.status = "idle"


@recover_on_exception
def c_starting(client, msg, obj):
    """
    Callback for the controller when a valid experiment configuration is received.

    It expects a "controller/command/start" message, which is the signal to start the experiment,
    and expects the experiment configuration to be loaded and validated.

    It then computes the intermediate setpoints and creates a list of instruments with expected config values.

    It updates the controller state and callback to "awaiting_instruments",
    publishes a message to start the instrument setup timer,
    and sends the instrument configuration for the instrument clients.
    """
    if msg.topic != "controller/command/start":
        if msg.topic == "controller/command/stop":
            c_stopping(client, msg, obj)
        elif msg.topic.startswith("controller/command/"):
            pub_err.incompatible_controller_status(obj, msg)
        return

    obj.status = "starting"
    # Create list of instrument state dicts from actuator variables
    for instrument_name in obj.config.instruments:
        if instrument_name not in obj.instrument_states:
            obj.instrument_states[instrument_name] = {
                "last_contact": None,
                "config": None,
                "state": None,
                "setpoints": None,
            }
    for spc_id in obj.config.spcs:
        if spc_id not in obj.spc_states:
            obj.spc_states[spc_id] = {"last_contact": None, "config": None}
    # Update state and callback of controller
    print(f"Awaiting instruments for experiment {obj.experiment_id}...")
    obj.status = "awaiting_instruments"
    client.callback = c_ready
    mqtt.MQTTPublisher.get_instance().publish(
        "controller/timer/command/start",
        json.dumps({"source": "instrument_setup", "experiment_id": obj.experiment_id}),
    )


@recover_on_exception
def c_ready(client, msg, obj):
    """
    Callback for the controller when instruments respond to the configuration.

    It expects a "controller/event/ready" message, which is the signal that all instruments are ready.
    This signal is generated by the timer client, once all instruments have responded to the configuration.

    The experiment is then ready to start, and a serial id is assigned to the experiment.

    The controller state and callback are updated to "running", and a message is published to start the experiment.
    """
    if msg.topic != "controller/event/ready":
        if msg.topic == "controller/command/stop":
            c_stopping(client, msg, obj)
        elif msg.topic.startswith("controller/command/"):
            pub_err.incompatible_controller_status(obj, msg)
        return

    print(f"Instruments ready, starting experiment {obj.experiment_id}...")
    obj.status = "ready"
    # Update state and callback of controller
    client.callback = c_running
    mqtt.MQTTPublisher.get_instance().publish(
        "controller/command/run", json.dumps({"experiment_id": obj.experiment_id})
    )


@recover_on_exception
def c_running(client, msg, obj):
    """
    Callback for the controller when the experiment is running.

    It expects a "controller/command/run" message, which is the signal to start the next setpoint.
    The message usually comes from the timer client, after the setpoint duration has passed.

    For each "controller/command/run" message, the controller publishes a setpoint, and keeps track of past and future setpoints.

    If there are no more setpoints, the controller updates its state and callback to "stopping",
    and publishes a message to end the experiment.
    """
    if msg.topic != "controller/command/run":
        if msg.topic == "controller/command/stop":
            c_stopping(client, msg, obj)
        elif msg.topic.startswith("controller/command/"):
            pub_err.incompatible_controller_status(obj, msg)
        return

    if obj.setpoints == []:
        if obj.current_setpoint is not None:
            obj.past_setpoints.append(obj.current_setpoint)
            obj.current_setpoint = None
        client.callback = c_stopping
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/event/end", json.dumps({"experiment_id": obj.experiment_id})
        )
        return

    if obj.current_setpoint is None:
        obj.status = "running"
    else:
        obj.past_setpoints.append(obj.current_setpoint)
    next_setpoint = obj.setpoints.pop(0)
    obj.current_setpoint = next_setpoint
    print(f"Next setpoint: {next_setpoint}")
    for column_name, value in next_setpoint.items():
        if column_name == "duration":
            continue
        instrument, variable = column_name.split("/", 1)
        mqtt.MQTTPublisher.get_instance().publish(
            f"instruments/{instrument}/{variable}/setpoint",
            json.dumps({"value": value}),
        )
    mqtt.MQTTPublisher.get_instance().publish(
        "controller/timer/command/start",
        json.dumps(
            {
                "source": "setpoint",
                "experiment_id": obj.experiment_id,
                "duration": next_setpoint["duration"],
            }
        ),
    )


@recover_on_exception
def c_stopping(client, msg, obj):
    """
    Callback for the controller when the experiment is stopping.

    This method is also called directly by any other callback whenever a controller/stop message is received.

    It dumps the experiment's database in the background, and stays stopping until it is done,
    when it resets the cstate object, and goes back to idle.

    Currently controller/stop and controller/end only differ in the final print.
    """
    if msg.topic not in [
        "controller/command/stop",
        "controller/event/end",
    ]:
        # A setpoint may end (controller/command/run) as the experiment is stopped
        if msg.topic.startswith("controller/command/") and (
            msg.topic != "controller/command/run"
        ):
            pub_err.incompatible_controller_status(obj, msg)
        return
    try:
        message = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.message_validation(e)
        return
    if message.get("experiment_id") == obj.experiment_id:
        if obj.status == "stopping":
            # Already stopping (e.g. stopped after it finished), until its database is dumped
            return
        obj.status = "stopping"
        client.callback = c_stopping
        uid = obj.experiment_id
        stop_reason = (
            "was stopped" if msg.topic == "controller/command/stop" else "finished"
        )

        def reset_once_dumped():
            # Unless the controller was already reset (e.g. by an exception) and moved on
            if obj.experiment_id != uid:
                return
            obj.reset()
            client.callback = c_idle
            print(f"Experiment {uid} {stop_reason} and the controller has been reset.")

        # In the background, so the controller keeps sending its heartbeats meanwhile
        dump_database_for_experiment(obj, on_done=reset_once_dumped)
    else:
        pub_err.incompatible_uid(obj, msg, message.get("experiment_id"), "controller")
