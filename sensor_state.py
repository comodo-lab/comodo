import ujson

import sensor 

class SensorState (object):
    def __init__(self):
        """ The state machine for the sensor

        Args:
            None

        Returns:
            None
        """
        
        self.status = {
            "name": "---",
            "status": "awaiting_config",
            "setpoint": None,
            "value": 0,
            "config": {
                "p": None,
                "i": None,
                "d": None,
                "tolerance": None
            },
        }

        self.client = None
        self.config = None
        self.sensor = None

    # Return string representation of the status
    def get_status(self):
        """ Return the status of the sensor

        Returns:
            str: The status of the sensor
        """
        
        return ujson.dumps(self.status)

    # Set the config
    def set_config(self, config):
        """ Set the configuration

        Args:
            config: dict: The configuration

        Returns:
            None
        """
        
        self.config = config

        
    def awaiting_config_cb(self, topic, msg):
        """ The callback function for the mqtt client when the sensor is awaiting config
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
        """ The callback function for the mqtt client when the sensor is awaiting setpoint
        Can move to the adjusting state if the setpoint is set

        Listens to: sensor/setpoint
        Next states: adjusting

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """

        if topic.decode("utf-8") == f"sensor/setpoint":
            params = ujson.loads(msg)
            self.status["setpoint"] = params[self.config['SENSOR_ID']]
            self.client.set_callback(self.adjusting_cb)
            self.status["status"] = "adjusting"

    def adjusting_cb(self, topic, msg):
        """ The callback function for the mqtt client when the sensor is adjusting
        Can move to the ready state if the sensor is ready

        Listens to: sensor/{SENSOR_ID}/setup
        Next states: ready

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
            
        distance = abs(self.status['value'] - self.status["setpoint"])
        if distance < self.status["config"]["tolerance"]:
            self.client.set_callback(self.ready_cb)
            self.status["status"] = "ready"        

    def ready_cb(self, topic, msg):
        """ The callback function for the mqtt client when the sensor is ready
        
        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None 
        """

        # Listen for new setpoint
        if topic.decode("utf-8") == "sensor/setpoint":
            params = ujson.loads(msg)
            self.status["setpoint"] = params[self.config['SENSOR_ID']]
            self.client.set_callback(self.adjusting_cb)
            self.status["status"] = "adjusting"

    def _apply_config(self, msg):
        """ Apply the configuration

        Args:
            msg: str: The message

        Returns:
            None
        """
        
        params = ujson.loads(msg)
        self.status["config"]["p"] = params["p"]
        self.status["config"]["i"] = params["i"]
        self.status["config"]["d"] = params["d"]
        self.status["config"]["tolerance"] = params["tolerance"]

        self.status["config"]["name"] = params["name"]
        self.sensor = sensor.BaseSensor.create_sensor(params["name"],
                                                      self.config["DUMMY"])

