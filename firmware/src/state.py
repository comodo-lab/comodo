import json
from typing import ClassVar

from src import instrument as inst

import utils.mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val


class InstrumentState:

    allowed_status: ClassVar[list[str]] = [
        "initialising",
        "awaiting_experiment",
        "running",
        "error",
        "safe_stop",
    ]

    __slots__: tuple[str, ...] = (
        "_client",
        "_instrument",
        "_status",
        "_can_measure",
        "_can_set_setpoint",
    )

    def __init__(self, config):
        """
        Initialise the InstrumentState object.

        Args:
            Config: dict: The configuration object

        Returns:
            None
        """
        topics = [
            "controller/command/start",
            f"instruments/{config['INSTRUMENT_NAME']}/configure",
            f"instruments/{config['INSTRUMENT_NAME']}/+/setpoint",
            "controller/event/end",
            "controller/command/stop",
        ]
        self._client = mqtt.MQTTClient(
            id=config["INSTRUMENT_NAME"],
            callback=self.initialising_cb,
            topics=topics,
            broker_address=config["MQTT_HOST"],
            user=config["MQTT_USER"],
            password=config["MQTT_PASS"],
            connection_timeout=60,
        )
        self._instrument = inst.create_instrument(config)
        self._can_measure = True
        self._can_set_setpoint = True
        self.status = "initialising"

    @property
    def client(self):
        """Get the MQTT client."""
        return self._client

    @property
    def instrument(self):
        """Get the instrument instance."""
        return self._instrument

    @property
    def status(self) -> str:
        """Get the current status of the instrument."""
        return self._status

    @status.setter
    def status(self, new_status):
        """Set the status of the instrument if valid, and update the MQTT client callback accordingly.
        The status cannot be changed during a safe stop: only reset() clears it, bypassing this setter.

        Args:
            new_status: str: The new status to set

        Returns:
            None
        """
        if new_status not in self.allowed_status:
            raise ValueError(f"Invalid status: {new_status}")
        if getattr(self, "_status", None) == "safe_stop":
            print(f"WARNING: Cannot update status from 'safe_stop' to '{new_status}'.")
            return

        self._status = new_status
        self.client.callback = getattr(self, f"{new_status}_cb")

    def publish_heartbeat(self):
        """
        Publish the heartbeat of the instrument to the MQTT broker.
        """
        heartbeat = json.dumps(
            {
                "state": {
                    "status": self.status,
                    "measurements": {
                        variable: self.instrument.previous_measurements.get(variable)
                        for variable in self.instrument.config["ACTIVE_VARIABLES"]
                    },
                },
                "setpoints": self.instrument.setpoints,
                "config": self.instrument.print_config(),
            }
        )
        try:
            mqtt.MQTTPublisher.get_instance().publish(
                f"instruments/{self.instrument.config['INSTRUMENT_NAME']}/heartbeat",
                heartbeat,
            )
        except mqtt.MQTTMessageError as e:
            # Not raised, so the instrument keeps running, and can safe stop
            print(f"WARNING: Could not publish heartbeat: {e}")

    def safe_stop(self, reason):
        """
        Sends every actuator to its safe stop setpoint, and ignores any further commands and setpoints until reset.
        The error is printed, and published if possible, as the broker may not be reachable.
        """
        self.status = "safe_stop"
        self.instrument.config["experiment"]["experiment_id"] = None
        message = f"[{self.instrument.config['INSTRUMENT_NAME']}] Safe stop triggered: {reason}"
        print(f"ERROR: {message}")
        for variable, setpoint in self.instrument.config["SAFE_STOP_SETPOINTS"].items():
            try:
                self.instrument.set_and_go_to_setpoint(variable, setpoint)
                print(f"Safe stop setpoint for {variable} applied: {setpoint}")
            except Exception as e:
                print(
                    f"ERROR: Failed to set the safe stop setpoint for {variable}: {e}"
                )
        try:
            mqtt.MQTTPublisher.get_instance().publish(
                "error/instrument",
                json.dumps({"code": "safe_stop", "message": message}),
            )
        except mqtt.MQTTMessageError as e:
            # Not raised, so the instrument keeps running
            print(f"WARNING: Could not publish safe stop: {e}")

    def initialising_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is starting up

        Listens to: None
        Next status: awaiting_experiment
        """
        print(
            f"WARNING: Received {msg.topic} while instrument is initialising. Ignoring..."
        )

    def awaiting_experiment_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is awaiting an experiment to start

        Listens to: controller/command/start, instruments/{name}/configure
        Next status: running
        """
        payload = mqtt_val.validate_message(msg.topic, msg.payload)
        if msg.topic.endswith("configure"):
            # Save live config
            for key, value in payload.items():
                self.instrument.config["experiment"][key] = value
        elif msg.topic.endswith("start"):
            # Save experiment id and move to running
            try:
                self.instrument.config["experiment"]["experiment_id"] = payload[
                    "experiment_id"
                ]
            except KeyError:
                print(
                    f"WARNING: Received {msg.topic} without an experiment id. Ignoring..."
                )
                return
            self.status = "running"
        elif msg.topic.endswith("setpoint"):
            self.running_cb(_client, msg, _obj)
        else:
            print(
                f"WARNING: Received {msg.topic} while instrument is awaiting experiment. Ignoring..."
            )

    def running_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is running

        Listens to: instruments/{name}/{variable}/setpoint, controller/event/end, controller/command/stop
        Next status: awaiting_experiment, error
        """
        if msg.topic in ["controller/event/end", "controller/command/stop"]:
            self.reset()
        elif msg.topic.endswith("setpoint"):
            # Extract variable name from topic: instruments/{name}/{variable}/setpoint
            _, _, variable, _ = msg.topic.split("/")
            # Parse incoming setpoint
            params = mqtt_val.validate_message(msg.topic, msg.payload)
            setpoint = params.get("value")
            # Check setpoint validity
            if not isinstance(setpoint, (int, float)) or setpoint == None:
                print(f"WARNING: Invalid setpoint received: {setpoint}")
                return
            if self.status == "safe_stop":
                print(f"WARNING: Ignoring setpoint for {variable} during safe stop.")
                return
            try:
                self.instrument.set_and_go_to_setpoint(variable, setpoint)
                self._can_set_setpoint = True
                if self.status == "error" and self._can_measure:
                    if (
                        self.instrument.config["experiment"].get("experiment_id")
                        is None
                    ):
                        self.status = "awaiting_experiment"
                    else:
                        self.status = "running"
            except Exception as e:
                self._can_set_setpoint = False
                print(f"ERROR: Failed to set the setpoint for {variable}: {e}")
                self.status = "error"
        else:
            print(
                f"WARNING: Received {msg.topic} while instrument is {self.status}. Ignoring..."
            )

    def reset(self):
        # Reset setpoints to default
        for variable, setpoint in self.instrument.config["DEFAULT_SETPOINTS"].items():
            self.instrument.set_and_go_to_setpoint(variable, setpoint)
        # Reset experiment id and move to awaiting_experiment
        self.instrument.config["experiment"]["experiment_id"] = None
        # Bypass status setter to allow status change from safe_stop to awaiting_experiment
        self._status = "awaiting_experiment"
        self.client.callback = self.awaiting_experiment_cb
        print(
            f"Instrument {self.instrument.config['INSTRUMENT_NAME']} awaiting experiment."
        )

    def error_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument cannot take measurements or set setpoints
        Refers to running callback.
        """
        if self.instrument.config["experiment"].get("experiment_id") is None:
            self.awaiting_experiment_cb(_client, msg, _obj)
        else:
            self.running_cb(_client, msg, _obj)

    def safe_stop_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is in a safe stop.
        Ignores everything. Only a reset clears it.

        Next status: awaiting_experiment (through a reset)
        """
        print(f"WARNING: Received {msg.topic} during safe stop. Ignoring...")
