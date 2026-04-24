import os
import json
import textwrap

import time as t

from utils import mqtt_clients as mqtt

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
    connected = False
    retries = 0
    while not connected and retries < 10:
        try:
            publisher = mqtt.MQTTPublisher.get_instance(
                broker_address=mqtt_host,
                user=mqtt_user,
                password=mqtt_pass,
                id=f"publisher_pid_{sensor}__{actuator}",
            )
            connected = True
        except Exception as e:
            print(f"Failed to connect to MQTT broker ({mqtt_host}): {e}. Retrying in 5s...")
            retries += 1
            t.sleep(5)
    
    if not connected:
        print("Could not connect to MQTT broker after 10 retries. Exiting.")
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

        # Extract instrument ID from sensor (e.g., 'pressure_upstream' from 'pressure_upstream/pressure')
        sensor_id = sensor.split("/")[0]

        # Initialize MQTT client
        self.pid_client = None
        retries = 0
        while self.pid_client is None and retries < 10:
            try:
                self.pid_client = mqtt.MQTTClient(
                    id=self.pid.id,
                    callback=SetpointController.on_sensor_message,
                    topics=[
                        f"instrument/{sensor_id}/setpoint",
                        f"measurement/{sensor}",
                        # f"sensor/{sensor}/setpoint_reached",
                        f"{self.pid.id}/setup",
                        "controller/pause",
                        "controller/stop",
                        "controller/end",
                    ],
                    broker_address=mqtt_host,
                    user=mqtt_user,
                    password=mqtt_pass,
                    obj=self,
                )
            except Exception as e:
                print(f"SetpointController client failed to connect to {mqtt_host}: {e}. Retrying...")
                retries += 1
                t.sleep(5)
        
        if self.pid_client is None:
            raise RuntimeError(f"SetpointController failed to connect after {retries} retries.")

        # no_setpoint
        # adjusting
        # ready
        # awaiting_config
        # Initialise status dictionary
        self.state = {
            "name": f"pid_{sensor}__{actuator}",
            "status": "no_setpoint",
            "setpoint": None,
            "config": self.pid.get_config(),
        }

        # Publish initial setpoint as None
        mqtt.MQTTPublisher.get_instance().publish(
            f"{self.pid.id}/setpoint",
            json.dumps({self.pid.sensor: None}),
        )

    @staticmethod  # Prevents passing 'self' as first argument, conflicting with MQTTClient callback signature
    def on_sensor_message(client, msg, spc):
        """Callback function for handling sensor messages."""
        try:
            message = mqtt.load_message(msg)
        except json.JSONDecodeError as e:
            error = f"Cannot decode {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
            print(f"ERROR: {error}")
            mqtt.MQTTPublisher.get_instance().publish(
                f"error/{spc.pid.id}",
                json.dumps({"error": error}),
            )
            spc.state["status"] = "error"
            spc.publish_heartbeat()
            return

        # Extract instrument ID from sensor (e.g., 'pressure_upstream' from 'pressure_upstream/pressure')
        sensor_id = spc.pid.sensor.split("/")[0]

        if msg.topic in ["controller/pause", "controller/stop", "controller/end"]:
            print(f"PID {spc.pid.id} silenced by {msg.topic}")
            spc.state["status"] = "no_setpoint"
            spc.state["setpoint"] = None
            spc.pid.setpoint = None
            # Extract instrument ID from actuator (e.g., 'massflow' from 'massflow/massflow')
            actuator_id = spc.pid.actuator.split("/")[0]
            # Publish None to stop the actuator if needed (optional, firmware usually holds)
            # mqtt.MQTTPublisher.get_instance().publish(f"instrument/{actuator_id}/setpoint", json.dumps({actuator_id: None}))
            return

        if msg.topic == f"instrument/{sensor_id}/setpoint":
            setpoint = message.get(sensor_id)
            if setpoint is not None:
                spc.state["status"] = "adjusting"
                spc.state["setpoint"] = setpoint
                spc.pid.setpoint = setpoint
                mqtt.MQTTPublisher.get_instance().publish(
                    f"{spc.pid.id}/setpoint",
                    json.dumps({spc.pid.sensor: setpoint}),
                )
            return
        elif msg.topic == f"measurement/{spc.pid.sensor}" or msg.topic.endswith(f"/{spc.pid.sensor}"):
            if spc.pid.setpoint is not None:
                spc.state["status"] = "adjusting"
                spc.state["setpoint"] = spc.pid.setpoint
                setpoint = spc.pid.step(message["value"], spc.pid.setpoint)
                
                # Extract instrument ID from actuator (e.g., 'massflow' from 'massflow/massflow')
                actuator_id = spc.pid.actuator.split("/")[0]
                
                mqtt.MQTTPublisher.get_instance().publish(
                    f"instrument/{actuator_id}/setpoint",
                    json.dumps({actuator_id: setpoint}),
                )
            return
        elif msg.topic == f"instrument/{spc.pid.sensor}/setpoint_reached":
            spc.state["status"] = "ready"
            spc.pid.setpoint = None
            mqtt.MQTTPublisher.get_instance().publish(
                f"{spc.pid.id}/setpoint_reached",
                json.dumps({spc.pid.sensor: True}),
            )
            return
        elif msg.topic == f"{spc.pid.id}/setup":
            not_configurable = []
            for k, v in message.items():
                if k not in spc.pid.configurable:
                    not_configurable.append(k)
            if not_configurable:
                spc.state["status"] = "error"
                e = ", ".join(not_configurable)
                error = f"Cannot configure PID parameter: {e}. Aborting setup."
                mqtt.MQTTPublisher.get_instance().publish(
                    f"error/{spc.pid.id}",
                    json.dumps({"error": error}),
                )
            else:
                for k, v in message.items():
                    setattr(spc.pid, k, v)
                spc.state["status"] = "reconfigured"
                spc.state["config"] = spc.pid.get_config()
                mqtt.MQTTPublisher.get_instance().publish(
                    f"heartbeat/{spc.pid.id}",
                    f"{spc.pid.get_state(1)}",
                )
            spc.publish_heartbeat()
            return

    def start_heartbeat_loop(self):
        """Start the heartbeat loop to publish PID state at regular intervals."""
        while self.pid.healthy:
            self.publish_heartbeat()
            t.sleep(self.heartbeat_interval)

    def publish_heartbeat(self):
        """Publish the current state of the SPC, including controller config."""
        mqtt.MQTTPublisher.get_instance().publish(
            f"heartbeat/{self.pid.id}",
            f"{json.dumps(self.state)}",
        )


if __name__ == "__main__":

    main()  # pragma: no cover
