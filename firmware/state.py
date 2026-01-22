import sys
import json
import sensor


class SensorState(object):
    def __init__(self):
        """The state machine for the sensor

        Args:
            None

        Returns:
            None
        """

        self.status = {
            "name": None,
            "status": "awaiting_config",
            "setpoint": None,
            "config": {"p": None, "i": None, "d": None, "tolerance": None},
        }

        self.client = None
        self.config = None
        self.sensor = None
        self.measurement = 0.0

    # Return string representation of the status
    def get_status(self):
        """Return the status of the sensor

        Returns:
            str: The status of the sensor
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

    def awaiting_config_cb(self, topic, msg):
        """The callback function for the mqtt client when the sensor is awaiting config
        Can move to the ready state if the setpoint is set

        Listens to: sensor/{SENSOR_ID}/setup
        Next states: ready

        Args:
           topic: str: The topic of the message
           msg: str: The message

        Returns:
            None
        """
            
        if topic.decode("utf-8") == f"sensor/{self.config['SENSOR_ID']}/setup":
            self._apply_config(msg)
            self.client.set_callback(self.no_setpoint_cb)
            self.status["status"] = "no_setpoint"

    def no_setpoint_cb(self, topic, msg):
        """The callback function for the mqtt client when the sensor is awaiting setpoint
        Can move to the adjusting state if the setpoint is set

        Listens to: sensor/{SENSOR_ID}/setpoint
        Next states: adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(topic, msg)

    def adjusting_cb(self, topic, msg):
        """The callback function for the mqtt client when the sensor is adjusting
        Can move to the ready state if the sensor is ready

        Listens to: sensor/{SENSOR_ID}/setpoint
                    sensor/{SENSOR_ID}/setpoint_reached
        Next states: ready, adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(topic, msg)

        if (topic.decode("utf-8") == f"sensor/{self.config['SENSOR_ID']}/setpoint_reached"):
            self.client.set_callback(self.ready_cb)
            self.status["status"] = "ready"

        # if controller/end is received, move to the awaiting_config state
        self._end_experiment(topic)

    def ready_cb(self, topic, msg):
        """The callback function for the mqtt client when the sensor is ready

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """

        # If setpoint is recieved and valid, go to it
        self._parse_and_go_to_setpoint(topic, msg)

        # if controller/end is received, move to the awaiting_config state
        self._end_experiment(topic)

    def _apply_config(self, msg):
        """Apply the configuration

        Args:
            msg: str: The message

        Returns:
            None
        """

        params = json.loads(msg)
        self.status["config"]["p"] = params["p"]
        self.status["config"]["i"] = params["i"]
        self.status["config"]["d"] = params["d"]
        self.status["config"]["tolerance"] = params["tolerance"]

        self.status["name"] = params["name"]
        self.sensor = sensor.BaseSensor.create_sensor(params["name"])

    def _parse_and_go_to_setpoint(self, topic, msg):
        if topic.decode("utf-8") != f"sensor/{self.config['SENSOR_ID']}/setpoint":
            return

        # Parse incoming setpoint
        params = json.loads(msg)
        self.status["setpoint"] = params[self.config["SENSOR_ID"]]

        # Set state
        self.client.set_callback(self.adjusting_cb)
        self.status["status"] = "adjusting"

        # Trigger go to setpoint
        if self.config['SIMULATE']:
            self.sensor.simulate_go_to_setpoint(self.status["setpoint"])
        else:
            self.sensor.go_to_setpoint(self.status["setpoint"])

        return

    def _end_experiment(self, topic):
        if topic.decode("utf-8") == "controller/end":
            self.client.set_callback(self.awaiting_config_cb)
            self.status["status"] = "awaiting_config"
        if topic.decode("utf-8") == f"controller/stop":
            self.client.set_callback(self.awaiting_config_cb)
            self.status["status"] = "awaiting_config"

        return
