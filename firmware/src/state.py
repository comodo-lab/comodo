import json
from typing import ClassVar

from src import instrument as inst

import utils.mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val


class InstrumentStatus:

    allowed_states: ClassVar[list[str]] = [
        "initialising",
        "adjusting",
        "ready",
        "error",
    ]

    __slots__: tuple[str, ...] = (
        "_client",
        "_instrument",
        "_state",
    )

    def __init__(self, config):
        """
        Initialise the InstrumentStatus object.

        Args:
            Config: dict: The configuration object

        Returns:
            None
        """
        topics = [
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
        self.state = "initialising"

    @property
    def client(self):
        """Get the MQTT client."""
        return self._client

    @property
    def instrument(self):
        """Get the instrument instance."""
        return self._instrument

    @property
    def state(self) -> str:
        """Get the current state of the instrument."""
        return self._state

    @state.setter
    def state(self, new_state):
        """Set the state of the instrument if valid, and update the MQTT client callback accordingly.

        Args:
            new_state: str: The new state to set

        Returns:
            None
        """
        if new_state not in self.allowed_states:
            raise ValueError(f"Invalid state: {new_state}")

        self._state = new_state
        self.client.callback = getattr(self, f"{new_state}_cb")

    # Return string representation of the status
    def publish_heartbeat(self):
        """
        Publish the heartbeat of the instrument to the MQTT broker.
        """
        heartbeat = json.dumps(
            {
                "state": self.state,
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
        Next states: ready
        """
        print(
            f"Warning: Received {msg.topic} while instrument is initialising. Ignoring..."
        )

    def adjusting_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is adjusting

        Listens to: instruments/{name}/{variable}/setpoint, controller/event/end, controller/command/stop
        Next states: ready, idle

        Returns:
            None
        """
        # If setpoint is received and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        # if controller/event/end is received, move to the idle state
        self._end_experiment(msg.topic)

    def ready_cb(self, _client, msg, _obj=None):
        """
        Callback function for the mqtt client when the instrument is ready.
        Behaviour is identical to adjusting state.
        """
        self.adjusting_cb(_client, msg, _obj)

    def _parse_and_go_to_setpoint(self, msg):
        if not msg.topic.endswith("setpoint"):
            return

        # Extract variable name from topic: instruments/{name}/{variable}/setpoint
        _, _, variable, _ = msg.topic.split("/")

        # Parse incoming setpoint
        params = mqtt_val.validate_message(msg.topic, msg.payload)
        setpoint = params.get("value")

        # Check setpoint validity
        if not isinstance(setpoint, (int, float)) or setpoint == None:
            print(f"Invalid setpoint received: {setpoint}")
            return

        # Set state
        self.state = "adjusting"

        # Trigger go to setpoint
        self.instrument.set_and_go_to_setpoint(variable, setpoint)

    def _end_experiment(self, topic):
        if topic in ["controller/event/end", "controller/command/stop"]:
            self.state = "idle"
            self.instrument.setpoints = self.instrument.config[
                "DEFAULT_SETPOINTS"
            ].copy()
            print(f"Instrument {self.instrument.config['INSTRUMENT_NAME']} idle.")
