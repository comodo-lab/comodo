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
            "name": None,
            "status": "awaiting_config",
            "setpoint": None,
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

    def awaiting_config_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is awaiting config
        Can move to the ready state if the setpoint is set

        Listens to: instrument/{INSTRUMENT_ID}/setup
        Next states: ready

        Args:
           topic: str: The topic of the message
           msg: str: The message

        Returns:
            None
        """
        if msg.topic == f"instrument/{self.config['INSTRUMENT_ID']}/setup":
            self._apply_config(mqtt.load_message(msg))
            self.client.callback = self.no_setpoint_cb
            self.status["status"] = "no_setpoint"
            print(f"Instrument {self.config['INSTRUMENT_ID']} configured.")

    def no_setpoint_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is awaiting setpoint
        Can move to the adjusting state if the setpoint is set

        Listens to: instrument/{INSTRUMENT_ID}/setpoint
        Next states: adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
        # If a new config is recieved, apply it
        self.awaiting_config_cb(_client, msg, _obj)

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        # if controller/end is received, move to the awaiting_config state
        self._end_experiment(msg.topic)

    def adjusting_cb(self, _client, msg, _obj=None):
        """The callback function for the mqtt client when the instrument is adjusting
        Can move to the ready state if the instrument is ready

        Listens to: instrument/{INSTRUMENT_ID}/setpoint
                    instrument/{INSTRUMENT_ID}/setpoint_reached
        Next states: ready, adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
        # If a new config is recieved, apply it
        self.awaiting_config_cb(_client, msg, _obj)

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        if msg.topic == f"instrument/{self.config['INSTRUMENT_ID']}/setpoint_reached":
            self.client.callback = self.ready_cb
            self.status["status"] = "ready"

        # if controller/end is received, move to the awaiting_config state
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
        self.awaiting_config_cb(_client, msg, _obj)

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(msg)

        # if controller/end is received, move to the awaiting_config state
        self._end_experiment(msg.topic)

    def _apply_config(self, params):
        """Apply the configuration

        Args:
            params: dict: The parsed configuration

        Returns:
            None
        """
        self.status["config"]["tolerance"] = params["tolerance"]

    def _parse_and_go_to_setpoint(self, msg):

        if msg.topic != f"instrument/{self.config['INSTRUMENT_ID']}/#/setpoint":
            return

        if self.client.callback == self.no_setpoint_cb:
            print(f"Instrument {self.config['INSTRUMENT_ID']} active.")

        # Parse incoming setpoint
        params = mqtt.load_message(msg)
        self.status["setpoint"] = params[self.config["INSTRUMENT_ID"]]

        # Set state
        self.client.callback = self.adjusting_cb
        self.status["status"] = "adjusting"

        # Trigger go to setpoint
        if self.config["SIMULATE"]:
            self.instrument.simulate_go_to_setpoint(self.status["setpoint"])
        else:
            self.instrument.go_to_setpoint(self.status["setpoint"])

        return

    def _end_experiment(self, topic):
        if topic in ["controller/end", "controller/stop"]:
            self.client.callback = self.awaiting_config_cb
            self.status["status"] = "awaiting_config"
            print(f"Instrument {self.config['INSTRUMENT_ID']} awaiting configuration.")

        return
