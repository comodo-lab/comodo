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

        Args:
            new_status: str: The new status to set

        Returns:
            None
        """
        if new_status not in self.allowed_status:
            raise ValueError(f"Invalid status: {new_status}")

        self._status = new_status
        self.client.callback = getattr(self, f"{new_status}_cb")

    def publish_heartbeat(self):
        """
        Publish the heartbeat of the instrument to the MQTT broker.
        """
        heartbeat = json.dumps(
            {
                "state": self.status,
                "setpoints": self.instrument.setpoints,
                "config": self.instrument.print_config(),
            }
        )
        if self.client is not None:
            self.client.publish(
                f"instruments/{self.instrument.config['INSTRUMENT_NAME']}/heartbeat",
                heartbeat,
            )

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
            # Save live config (calibration)
            self.instrument.config["experiment"] = payload
        elif msg.topic.endswith("start"):
            # Save experiment id and move to running
            try:
                self.instrument.config["experiment"]["id"] = payload["experiment_id"]
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
            # Trigger go to setpoint
            try:
                self.instrument.set_and_go_to_setpoint(variable, setpoint)
                self._can_set_setpoint = True
                if self.status == "error" and self._can_measure:
                    if self.instrument.config["experiment"].get("id") is None:
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
        self.instrument.config["experiment"]["id"] = None
        self.status = "awaiting_experiment"
        print(
            f"Instrument {self.instrument.config['INSTRUMENT_NAME']} awaiting experiment."
        )

    def error_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument cannot take measurements or set setpoints
        Refers to running callback.
        """
        if self.instrument.config["experiment"].get("id") is None:
            self.awaiting_experiment_cb(_client, msg, _obj)
        else:
            self.running_cb(_client, msg, _obj)
