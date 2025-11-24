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
    mqtt_host = os.getenv("MQTT_HOST")
    mqtt_user = os.getenv("MQTT_USER")
    mqtt_pass = os.getenv("MQTT_PASS")

    sensor = os.getenv("SENSOR")
    actuator = os.getenv("ACTUATOR")

    pid = PID(
        id=f"pid/{sensor}__{actuator}",
        sensor=sensor,
        actuator=actuator,
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
