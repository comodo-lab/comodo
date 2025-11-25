import os
import json
import textwrap

import time as t

from utils.mqtt_clients import MQTTClient, MQTTPublisher, load_message
from src.pid import PID


def main():
    print(f"Starting...")
    # Load configuration
    heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", 1))
    try:
        mqtt_host = os.getenv("MQTT_HOST")
        mqtt_user = os.getenv("MQTT_USER")
        mqtt_pass = os.getenv("MQTT_PASS")

        sensor = os.getenv("SENSOR")
        actuator = os.getenv("ACTUATOR")
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
        exit(1)

    k_p = os.getenv("K_P", None)
    k_i = os.getenv("K_I", None)
    k_d = os.getenv("K_D", None)
    k_aw = os.getenv("K_AW", None)
    k_df = os.getenv("K_DF", None)
    max_output = os.getenv("OUT_MAX", None)
    min_output = os.getenv("OUT_MIN", None)
    max_rate_output = os.getenv("OUT_MAX_R", None)

    # create dict of PID parameters and filter out None values
    pid_params = {
        k: float(v)
        for k, v in {
            "k_p": k_p,
            "k_i": k_i,
            "k_d": k_d,
            "k_aw": k_aw,
            "k_df": k_df,
            "max": max_output,
            "min": min_output,
            "max_rate": max_rate_output,
        }.items()
        if v is not None
    }

    pid = PID(
        id=f"pid/{sensor}__{actuator}",
        sensor=sensor,
        actuator=actuator,
        **pid_params,  # unpack PID parameters
    )

    # Initialize MQTT client
    pid_client = MQTTClient(
        id=pid.id,
        callback=on_sensor_message,
        topics=[f"sensor/{sensor}/setpoint", f"measurement/{sensor}"],
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        obj=pid,
    )

    # Start heartbeat loop
    while pid.healthy:
        MQTTPublisher.get_instance().publish(
            f"heartbeat/{pid.id}",
            f"{pid.get_state()}",
        )
        t.sleep(heartbeat_interval)

    print(f"Exiting...")


if __name__ == "__main__":

    main()


def on_sensor_message(client, msg, pid):
    """Callback function for handling sensor messages."""
    try:
        message = load_message(msg)
    except json.JSONDecodeError as e:
        error = f"Error decoding {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
        MQTTPublisher.get_instance().publish(
            f"error/{pid.id}",
            json.dumps({"error": error}),
        )
        return

    if msg.topic == f"sensor/{pid.sensor}/setpoint":
        setpoint = message.get(pid.sensor)
        if setpoint:
            pid.setpoint = setpoint
        return
    elif msg.topic == f"measurement/{pid.sensor}":
        if pid.setpoint is not None:
            setpoint = pid.step(message["value"], pid.setpoint)
            MQTTPublisher.get_instance().publish(
                f"sensor/{pid.actuator}/setpoint",
                json.dumps({pid.actuator: setpoint}),
            )
        return
