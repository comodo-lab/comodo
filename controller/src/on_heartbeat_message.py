import json
import time as t

from utils import mqtt_clients as mqtt
import utils.mqtt_validator as mqtt_val

import src.publish_error as pub_err


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from an instrument
    or a setpoint controller.
    It expects a message compliant with the spec schema for that channel.
    """
    source = msg.topic.split("/")[0]
    if source not in ["instruments", "setpoint_controllers"] or not msg.topic.endswith(
        "/heartbeat"
    ):
        pub_err.incompatible_topic(obj, msg, "heartbeat_callback")
        return

    try:
        message = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        # maintain a clean slate for instruments before the awaiting_instruments state
        return

    if source == "setpoint_controllers":
        spc_id = msg.topic.split("/")[1]
        if spc_id in obj.spc_states:
            handle_spc_heartbeat(obj, message, spc_id)
        else:
            pub_err.unconfigured_spc(msg, spc_id)
        return

    instrument_name = msg.topic.split("/")[1]
    if instrument_name in obj.instrument_states:
        handle_instrument_heartbeat(obj, message, instrument_name)
    else:
        pub_err.unconfigured_instrument(msg, instrument_name)
        return


def handle_instrument_heartbeat(obj, heartbeat, instrument_name):
    # Update instrument state and setpoints
    obj.instrument_states[instrument_name]["last_contact"] = t.time()
    if not heartbeat_valid(obj, heartbeat, instrument_name):
        return
    obj.instrument_states[instrument_name]["state"] = heartbeat["state"]
    obj.instrument_states[instrument_name]["setpoints"] = heartbeat["setpoints"]
    obj.instrument_states[instrument_name]["config"] = heartbeat["config"]
    if obj.status == "awaiting_instruments":
        # Assert state and config match, otherwise stop experiment
        if heartbeat["state"]["status"] in ["initialising", "awaiting_experiment"]:
            return
        check_ready(obj)


def handle_spc_heartbeat(obj, heartbeat, spc_id):
    obj.spc_states[spc_id]["last_contact"] = t.time()
    if not spc_heartbeat_valid(obj, heartbeat, spc_id):
        return
    obj.spc_states[spc_id]["config"] = heartbeat["config"]
    if obj.status == "awaiting_instruments":
        check_ready(obj)


def check_ready(obj):
    """
    Checks if all instruments are running and all setpoint controllers have reported
    the expected config, and if so: sets the configured flag and publishes ready event.
    """
    heartbeats_ready = all(
        (instrument["state"] or {}).get("status") in ["running"]
        for instrument in obj.instrument_states.values()
    ) and all(spc["config"] is not None for spc in obj.spc_states.values())

    if heartbeats_ready and not obj.instruments_ready:
        obj.instruments_ready = True
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/event/ready",
            json.dumps({"experiment_id": obj.experiment_id}),
        )


def heartbeat_valid(obj, heartbeat, instrument_name):
    expected = obj.get_expected_heartbeat(instrument_name)
    if heartbeat["config"] != expected:
        # Tolerate experiment config miss-match if in a settling status
        if obj.status in ["awaiting_instruments", "stopping", "error"]:
            return False
        pub_err.invalid_instrument_config(
            instrument_name, expected, heartbeat["config"]
        )
        print("Stopping experiment...")
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/command/stop", json.dumps({"experiment_id": obj.experiment_id})
        )
        return False
    return True


def spc_heartbeat_valid(obj, heartbeat, spc_id):
    """
    Checks the PID values reported by a setpoint controller match the ones sent in the
    live config. Only the parameters sent are checked, the rest are left as they are.
    """
    expected = (obj.get_expected_spc_config(spc_id) or {}).get("pid", {})
    received = {k: heartbeat["config"]["pid"].get(k) for k in expected}
    if received != expected:
        # Tolerate experiment config miss-match if in a settling status
        if obj.status in ["awaiting_instruments", "stopping", "error"]:
            return False
        pub_err.invalid_spc_config(spc_id, expected, received)
        print("Stopping experiment...")
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/command/stop", json.dumps({"experiment_id": obj.experiment_id})
        )
        return False
    return True
