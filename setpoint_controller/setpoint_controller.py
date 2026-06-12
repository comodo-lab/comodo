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

        sensor_name, sensor_var = os.getenv("SENSOR").split("/", 1)
        actuator_name, actuator_var = os.getenv("ACTUATOR").split("/", 1)
    except KeyError as e:
        print(f"Missing required environment variable: {e}")
        exit(1)

    spc_id = f"{sensor_name}-{sensor_var}--{actuator_name}-{actuator_var}"

    # Initialise publisher singleton
    publisher = mqtt.MQTTPublisher.get_instance(
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        id=f"publisher_{spc_id}",
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
        spc_id=spc_id,
        sensor_name=sensor_name,
        sensor_var=sensor_var,
        actuator_name=actuator_name,
        actuator_var=actuator_var,
        **pid_params,
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
        spc_id: str,
        sensor_name: str,
        sensor_var: str,
        actuator_name: str,
        actuator_var: str,
        **pid_params,
    ):
        self.heartbeat_interval = heartbeat_interval
        self.sensor_name = sensor_name
        self.sensor_var = sensor_var
        self.actuator_name = actuator_name
        self.actuator_var = actuator_var
        self.spc_id = spc_id

        # Initialize PID controller
        self.pid = PID(
            id=spc_id,
            sensor=f"{sensor_name}/{sensor_var}",
            actuator=f"{actuator_name}/{actuator_var}",
            **pid_params,
        )

        # Initialize MQTT client
        self.pid_client = mqtt.MQTTClient(
            id=spc_id,
            callback=SetpointController.on_message,
            topics=[
                f"instruments/{sensor_name}/{sensor_var}/setpoint",
                f"instruments/{sensor_name}/{sensor_var}/measurement",
                f"setpoint_controller/{spc_id}/setup",
            ],
            broker_address=mqtt_host,
            user=mqtt_user,
            password=mqtt_pass,
            obj=self,
        )

        # Initialise status dictionary (spec format)
        self.status = {
            "state": "idle",
            "setpoints": {},
            "config": {
                "sensor": f"{sensor_name}/{sensor_var}",
                "actuator": f"{actuator_name}/{actuator_var}",
                "active": True,
                "k_p": self.pid.k_p,
                "k_i": self.pid.k_i,
                "k_d": self.pid.k_d,
                "k_aw": self.pid.k_aw,
                "k_df": self.pid.k_df,
                "max": self.pid.max,
                "min": self.pid.min,
                "max_rate": self.pid.max_rate,
                "experiment_id": None,
            },
        }

    @staticmethod
    def on_message(client, msg, spc):
        """Callback function for handling sensor messages."""
        try:
            message = mqtt.load_message(msg)
        except json.JSONDecodeError as e:
            error = f"Cannot decode {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
            print(f"ERROR: {error}")
            mqtt.MQTTPublisher.get_instance().publish(
                "error/setpoint_controller",
                json.dumps({"code": "json_decode_error", "message": error}),
            )
            spc.status["state"] = "error"
            spc.publish_heartbeat()
            return

        if msg.topic == f"instruments/{spc.sensor_name}/{spc.sensor_var}/setpoint":
            value = message.get("value")
            if value is not None:
                spc.status["state"] = "adjusting"
                spc.status["setpoints"][spc.sensor_var] = value
                spc.pid.setpoint = value
            return

        elif msg.topic == f"instruments/{spc.sensor_name}/{spc.sensor_var}/measurement":
            if spc.pid.setpoint is not None:
                spc.status["state"] = "adjusting"
                output = spc.pid.step(message["value"], spc.pid.setpoint)
                mqtt.MQTTPublisher.get_instance().publish(
                    f"instruments/{spc.actuator_name}/{spc.actuator_var}/setpoint",
                    json.dumps({"value": output}),
                )
            return

        elif msg.topic == f"setpoint_controller/{spc.spc_id}/setup":
            not_configurable = []
            for k, v in message.items():
                if k not in spc.pid.configurable:
                    not_configurable.append(k)
            if not_configurable:
                spc.status["state"] = "error"
                e = ", ".join(not_configurable)
                error = f"Cannot configure PID parameter: {e}. Aborting setup."
                mqtt.MQTTPublisher.get_instance().publish(
                    "error/setpoint_controller",
                    json.dumps({"code": "configuration_error", "message": error}),
                )
            else:
                for k, v in message.items():
                    setattr(spc.pid, k, v)
                spc.status["state"] = "idle"
                config = spc.pid.get_config()
                config["experiment_id"] = spc.status["config"]["experiment_id"]
                config["sensor"] = spc.status["config"]["sensor"]
                config["actuator"] = spc.status["config"]["actuator"]
                config["active"] = spc.status["config"]["active"]
                spc.status["config"] = config
            spc.publish_heartbeat()
            return

    def start_heartbeat_loop(self):
        """Start the heartbeat loop to publish PID state at regular intervals."""
        while self.pid.healthy:
            self.publish_heartbeat()
            t.sleep(self.heartbeat_interval)

    def publish_heartbeat(self):
        """Publish the current state of the SPC, including controller config."""
        print(f"Heartbeat from {self.spc_id}...")
        mqtt.MQTTPublisher.get_instance().publish(
            f"setpoint_controller/{self.spc_id}/heartbeat",
            json.dumps(self.status),
        )


if __name__ == "__main__":
    main()  # pragma: no cover
