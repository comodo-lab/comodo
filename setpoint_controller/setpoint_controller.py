import os
import json
import textwrap

import time as t

from utils import mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val

from src.pid import PID


def main():
    print(f"Starting...")
    # Load configuration
    heartbeat_interval = float(os.getenv("HEARTBEAT_INTERVAL", "1.0"))
    try:
        req_env_vars = ["MQTT_HOST", "MQTT_USER", "MQTT_PASS", "SENSOR", "ACTUATOR"]
        # Load required environment variables into a dictionary
        rev_dict = {key: os.getenv(key) for key in req_env_vars}
        # Check for missing values
        missing_req_env_vars = [k for k, v in rev_dict.items() if v is None]
        if missing_req_env_vars:
            raise KeyError(", ".join(missing_req_env_vars))
        # Validate SENSOR and ACTUATOR format
        if rev_dict["SENSOR"].count("/") != 1:
            raise ValueError("SENSOR must be instrument_name/variable_name")
        if rev_dict["ACTUATOR"].count("/") != 1:
            raise ValueError("ACTUATOR must be instrument_name/variable_name")

        mqtt_host = rev_dict["MQTT_HOST"]
        mqtt_user = rev_dict["MQTT_USER"]
        mqtt_pass = rev_dict["MQTT_PASS"]
        sensor_instrument, sensor_variable = rev_dict["SENSOR"].split("/", 1)
        actuator_instrument, actuator_variable = rev_dict["ACTUATOR"].split("/", 1)
    except KeyError as e:
        print(f"Missing required environment variables: {e}")
        exit(1)
    except ValueError as e:
        print(f"Invalid environment variable: {e}")
        exit(1)

    spc_id = f"{sensor_instrument}-{sensor_variable}--{actuator_instrument}-{actuator_variable}"

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
    spc = SetpointController(
        mqtt_host=mqtt_host,
        mqtt_user=mqtt_user,
        mqtt_pass=mqtt_pass,
        heartbeat_interval=heartbeat_interval,
        spc_id=spc_id,
        sensor_instrument=sensor_instrument,
        sensor_variable=sensor_variable,
        actuator_instrument=actuator_instrument,
        actuator_variable=actuator_variable,
        **pid_params,
    )

    spc.start_heartbeat_loop()

    print(f"Exiting...")


class SetpointController:
    """Setpoint controller, which has a PID controller and its MQTT client."""

    class Status:
        """Setpoint controller orchestration status. PID values live only in the PID."""

        __slots__ = [
            "_enabled",
            "_state",
            "_sensor_setpoint",
            "_sensor_measurement",
            "_actuator_setpoint",
            "experiment_id",
        ]

        item_keys = tuple(slot.lstrip("_") for slot in __slots__)

        allowed_state = [
            "idle",
            "adjusting",
            "ready",
            "error",
        ]

        def __init__(self):
            self._enabled = True
            self._state = "idle"
            self._sensor_setpoint = None
            self._sensor_measurement = None
            self._actuator_setpoint = None
            self.experiment_id = None

        def as_dict(self):
            return {
                "status": {
                    "state": self.state,
                    "enabled": self.enabled,
                    "sensor_measurement": self.sensor_measurement,
                    "actuator_setpoint": self.actuator_setpoint,
                    "experiment_id": self.experiment_id,
                },
                "setpoints": {
                    "sensor_setpoint": self.sensor_setpoint,
                },
            }

        @property
        def enabled(self) -> bool:
            return self._enabled

        @enabled.setter
        def enabled(self, value: bool):
            if not isinstance(value, bool):
                raise TypeError(f"Enabled must be a boolean value, got {type(value)}")
            self._enabled = value
            if not value:
                self._state = "idle"
                self._sensor_setpoint = None
                self._sensor_measurement = None
                self._actuator_setpoint = None
                self.experiment_id = None

        @property
        def state(self) -> str:
            return self._state

        @state.setter
        def state(self, value: str):
            if value not in self.allowed_state:
                raise ValueError(
                    f"Invalid state: {value}. Allowed values are: {self.allowed_state}"
                )
            self._state = value
            if value == "idle":
                self._sensor_setpoint = None
                self._sensor_measurement = None
                self._actuator_setpoint = None
                self.experiment_id = None

        @property
        def sensor_setpoint(self):
            return getattr(self, "_sensor_setpoint", None)

        @sensor_setpoint.setter
        def sensor_setpoint(self, value: float):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Sensor setpoint must be a float value, got {type(value)}"
                )
            self._sensor_setpoint = value

        @property
        def sensor_measurement(self):
            return getattr(self, "_sensor_measurement", None)

        @sensor_measurement.setter
        def sensor_measurement(self, value: float):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Sensor measurement must be a float value, got {type(value)}"
                )
            self._sensor_measurement = value

        @property
        def actuator_setpoint(self):
            return getattr(self, "_actuator_setpoint", None)

        @actuator_setpoint.setter
        def actuator_setpoint(self, value: float):
            if not isinstance(value, (int, float)):
                raise TypeError(
                    f"Actuator setpoint must be a float value, got {type(value)}"
                )
            self._actuator_setpoint = value

    def __init__(
        self,
        mqtt_host: str,
        mqtt_user: str,
        mqtt_pass: str,
        heartbeat_interval: float,
        spc_id: str,
        sensor_instrument: str,
        sensor_variable: str,
        actuator_instrument: str,
        actuator_variable: str,
        **pid_params,
    ):
        self.heartbeat_interval = heartbeat_interval
        self.sensor_instrument = sensor_instrument
        self.sensor_variable = sensor_variable
        self.actuator_instrument = actuator_instrument
        self.actuator_variable = actuator_variable
        self.spc_id = spc_id

        # Initialize PID controller
        self.pid = PID(
            **pid_params,
        )

        # Initialize MQTT client
        self.client = mqtt.MQTTClient(
            id=spc_id,
            callback=SetpointController.on_message,
            topics=[
                f"instruments/{sensor_instrument}/{sensor_variable}/setpoint",
                f"instruments/{sensor_instrument}/{sensor_variable}/measurement",
                f"setpoint_controller/{spc_id}/setup",
            ],
            broker_address=mqtt_host,
            user=mqtt_user,
            password=mqtt_pass,
            obj=self,
        )

        self.status = SetpointController.Status()

    @staticmethod  # Prevents passing 'self' as first argument, conflicting with MQTTClient callback signature
    def on_message(client, msg, spc):
        """Callback function for handling sensor messages."""
        try:
            message = mqtt_val.validate_message(msg.topic, msg.payload)
        except mqtt_val.MQTTValidationException as e:
            mqtt_val.print_and_publish_error("error/setpoint_controller", e)
            spc.status.state = "error"
            spc.publish_heartbeat()
            return

        if msg.topic == f"setpoint_controller/{spc.spc_id}/setup":
            for k, v in message.items():
                if k not in ["enabled", "experiment_id", "pid"]:
                    error = f"Cannot configure spc parameter: {k}. Aborting setup."
                    mqtt.MQTTPublisher.get_instance().publish(
                        "error/setpoint_controller",
                        json.dumps(
                            {"code": "spc_configuration_error", "message": error}
                        ),
                    )
                    spc.publish_heartbeat()
                    return
            enabled = message.get("enabled", None)
            experiment_id = message.get("experiment_id", None)
            pid_config = message.get("pid", {})
            not_configurable = []
            for k, v in pid_config.items():
                if k not in spc.pid.configurable:
                    not_configurable.append(k)
            if not_configurable:
                e = ", ".join(not_configurable)
                error = f"Cannot configure PID parameter: {e}. Aborting setup."
                mqtt.MQTTPublisher.get_instance().publish(
                    "error/setpoint_controller",
                    json.dumps({"code": "pid_configuration_error", "message": error}),
                )
            else:
                if enabled is not None:
                    spc.status.enabled = enabled
                if experiment_id is not None:
                    spc.status.experiment_id = experiment_id
                for k, v in pid_config.items():
                    setattr(spc.pid, k, v)
            spc.publish_heartbeat()
            return

        if spc.status.enabled is True:
            if (
                msg.topic
                == f"instruments/{spc.sensor_instrument}/{spc.sensor_variable}/setpoint"
            ):
                spc.status.sensor_setpoint = message.get("value")
                return

            elif (
                msg.topic
                == f"instruments/{spc.sensor_instrument}/{spc.sensor_variable}/measurement"
            ):
                spc.status.sensor_measurement = message.get("value")
                if (
                    spc.status.sensor_setpoint is not None
                    and spc.status.sensor_measurement is not None
                ):
                    spc.status.state = "adjusting"
                    spc.status.actuator_setpoint = spc.pid.step(
                        spc.status.sensor_measurement, spc.status.sensor_setpoint
                    )
                    mqtt.MQTTPublisher.get_instance().publish(
                        f"instruments/{spc.actuator_instrument}/{spc.actuator_variable}/setpoint",
                        json.dumps({"value": spc.status.actuator_setpoint}),
                    )
                return

    def start_heartbeat_loop(self):
        """Start the heartbeat loop to publish SPC state at regular intervals."""
        while self.pid.healthy:
            self.publish_heartbeat()
            t.sleep(self.heartbeat_interval)

    def publish_heartbeat(self):
        """Publish the current state of the SPC, including PID controller config."""
        heartbeat = self.status.as_dict()
        heartbeat["config"] = {
            "sensor": f"{self.sensor_instrument}/{self.sensor_variable}",
            "actuator": f"{self.actuator_instrument}/{self.actuator_variable}",
            "pid": self.pid.get_config(),
        }
        mqtt.MQTTPublisher.get_instance().publish(
            f"setpoint_controller/{self.spc_id}/heartbeat",
            json.dumps(heartbeat),
        )


if __name__ == "__main__":
    main()  # pragma: no cover
