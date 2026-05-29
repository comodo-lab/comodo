import sys
import json
import utils.mqtt_clients as mqtt


class InstrumentState(object):
    def __init__(self):
        """The state machine for the instrument

        Args:
            None

        Returns:
            None
        """

        self.status = {
            "state": "idle",
            "setpoints": {},
            "config": {"tolerance": None},
        }

        self.client = None
        self.config = None
        self.instrument = None
        self.measurement = 0.0

    # Return string representation of the status
    def get_status(self):
        """Return the status of the instrument

        Returns:
            str: The status of the instrument
        """

        return json.dumps(self.status)

    # Set the config
    def set_config(self, config):
        """Set the configuration

        Args:
            config: dict: The configuration

        Returns:
            None
        """

        self.config = config

    def idle_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is idle
        Can move to the ready state if the instrument is configured

        Listens to: instruments/{INSTRUMENT_ID}/setup
        Next states: ready

        Args:
           topic: str: The topic of the message
           msg: str: The message

        Returns:
            None
        """
        if msg.topic == f"instruments/{self.config['INSTRUMENT_ID']}/setup":
            self._apply_config(mqtt.load_message(msg))
            self.client.callback = self.ready_cb
            self.status["state"] = "ready"
            print(f"Instrument configured: {self.status['config']}")

    def adjusting_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is adjusting
        Can move to the ready state if the instrument is ready

        Listens to: instruments/{INSTRUMENT_ID}/+/setpoint
        Next states: ready, adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
        # If a new config is recieved, apply it
        self.idle_cb(_client, msg, _obj)

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        # if controller/event/end is received, move to the idle state
        self._end_experiment(msg.topic)

    def ready_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is ready

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
        # If a new config is recieved, apply it
        self.idle_cb(_client, msg, _obj)

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        # if controller/event/end is received, move to the idle state
        self._end_experiment(msg.topic)

    def _apply_config(self, params):
        """Apply the configuration

        Args:
            params: dict: The parsed configuration

        Returns:
            None
        """
        config = params.get("config", {})
        print(f"Instrument configuration received: {config}")
        for key in config:
            self.status["config"][key] = config[key]

    def _parse_and_go_to_setpoint(self, msg):
        if not msg.topic.endswith("setpoint"):
            return

        # Extract variable name from topic: instruments/{name}/{variable}/setpoint
        _, _, variable, _ = msg.topic.split("/")

        # Parse incoming setpoint
        params = mqtt.load_message(msg)
        setpoint = params.get("value")

        # Check setpoint validity and store
        if not isinstance(setpoint, (int, float)) or setpoint == None:
            print(f"Invalid setpoint received: {setpoint}")
            return
        self.status["setpoints"][variable] = setpoint

        # Set state
        self.client.callback = self.adjusting_cb
        self.status["state"] = "adjusting"

        # Trigger go to setpoint
        if self.config["SIMULATE"]:
            self.instrument.simulate_go_to_setpoint(self)
        else:
            self.instrument.go_to_setpoint(self)

        return

    def _end_experiment(self, topic):
        if topic in ["controller/event/end", "controller/command/stop"]:
            self.client.callback = self.idle_cb
            self.status["state"] = "idle"
            print(f"Instrument {self.config['INSTRUMENT_ID']} awaiting configuration.")

        return
