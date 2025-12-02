import os
import json
import textwrap

import time as t

from utils.mqtt_clients import MQTTClient, MQTTPublisher, load_message
from src.pid import PID


def main():
    print(f"Starting...")
    # Load configuration
    heartbeat_interval = float(os.getenv("HEARTBEAT_INTERVAL", 1)) / 1000
    try:
        mqtt_host = os.getenv("MQTT_HOST")
        mqtt_user = os.getenv("MQTT_USER")
        mqtt_pass = os.getenv("MQTT_PASS")

        sensor = os.getenv("SENSOR")
        actuator = os.getenv("ACTUATOR")
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
        exit(1)

    # Initialise publisher singleton
    publisher = MQTTPublisher.get_instance(
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        id=f"publisher_pid_{sensor}__{actuator}",
    )

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

    # Create SetpointController instance
    controller = SetpointController(
        mqtt_host=mqtt_host,
        mqtt_user=mqtt_user,
        mqtt_pass=mqtt_pass,
        heartbeat_interval=heartbeat_interval,
        sensor=sensor,
        actuator=actuator,
        **pid_params,  # unpack PID parameters
    )

    controller.start_heartbeat_loop()

    print(f"Exiting...")


class SetpointController:
    """Setpoint controller, which has a PID controller and its MQTT client."""

    def __init__(
        self,
        mqtt_host: str,
        mqtt_user: str,
        mqtt_pass: str,
        heartbeat_interval: int,
        sensor: str,
        actuator: str,
        **pid_params,
    ):
        self.heartbeat_interval = heartbeat_interval

        # Initialize PID controller
        self.pid = PID(
            id=f"pid/{sensor}__{actuator}",
            sensor=sensor,
            actuator=actuator,
            **pid_params,  # unpack PID parameters
        )

        # Initialize MQTT client
        self.pid_client = MQTTClient(
            id=self.pid.id,
            callback=SetpointController.on_sensor_message,
            topics=[f"sensor/{sensor}/setpoint", f"measurement/{sensor}"],
            broker_address=mqtt_host,
            user=mqtt_user,
            password=mqtt_pass,
            obj=self.pid,
        )

        # Publish initial setpoint as None
        MQTTPublisher.get_instance().publish(
            f"{self.pid.id}/setpoint",
            json.dumps({self.pid.sensor: None}),
        )

    @staticmethod  # Prevents passing 'self' as first argument, conflicting with MQTTClient callback signature
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
                MQTTPublisher.get_instance().publish(
                    f"{pid.id}/setpoint",
                    json.dumps({pid.sensor: setpoint}),
                )
            return
        elif msg.topic == f"measurement/{pid.sensor}":
            if pid.setpoint is not None:
                setpoint = pid.step(message["value"], pid.setpoint)
                MQTTPublisher.get_instance().publish(
                    f"sensor/{pid.actuator}/setpoint",
                    json.dumps({pid.actuator: setpoint}),
                )
            return

    def start_heartbeat_loop(self):
        """Start the heartbeat loop to publish PID state at regular intervals."""
        while self.pid.healthy:
            MQTTPublisher.get_instance().publish(
                f"heartbeat/{self.pid.id}",
                f"{self.pid.get_state()}",
            )
            t.sleep(self.heartbeat_interval)


if __name__ == "__main__":

    main()
