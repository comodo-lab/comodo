# Description: This file contains the state machine class and the sensor state class
# When an MQTT message is recieved, a callback function is returned, which changes the behaviour of the state machine

import ujson

class SensorState (object):
    def __init__(self):
        self.status = {
            "name": "---",
            "status": "idle",
            "setpoint": None,
            "temperture": 0,
            "config": {
                "p": None,
                "i": None,
                "d": None,
                "tolerance": None
            },
        }

        self.client = None
        self.config = None

    # Return string representation of the status
    def get_status(self):
        return ujson.dumps(self.status)

    # Set the config
    def set_config(self, config):
        self.config = config

    def idle_cb(self, topic, msg):
        """ The callback function for the mqtt client when the sensor is idle
        Can move to the ready state if the setpoint and config are set
        Otherwise can move to the awaiting_config or awaiting_setpoint state 

        Listens to: sensor/{SENSOR_ID}/setup, sensor/setpoint
        Next states: ready, awaiting_config, awaiting_setpoint

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """
        
        if topic.decode("utf-8") == f"sensor/{self.config['SENSOR_ID']}/setup":
            self._apply_config(msg)

            # Set the status to ready if the setpoint is set
            if self.status["setpoint"] is not None:
                self.client.set_callback(self.ready_cb)
                self.status["status"] = "ready"
            else:
                self.client.set_callback(self.awaiting_setpoint_cb)
                self.status["status"] = "awaiting_setpoint"
            
        if topic.decode("utf-8") == f"sensor/setpoint":
            params = ujson.loads(msg)
            self.status["setpoint"] = params[self.config['SENSOR_ID']]

            # Set the status to ready if the config is set
            if self.status["config"]["p"] is not None:
                self.client.set_callback(self.ready_cb)
                self.status["status"] = "ready"
            else:
                self.client.set_callback(self.awaiting_config_cb)
                self.status["status"] = "awaiting_config"


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
            self.client.set_callback(self.ready_cb)
            self.status["status"] = "ready"

    def awaiting_setpoint_cb(self, topic, msg):
        """ The callback function for the mqtt client when the sensor is awaiting setpoint
        Can move to the ready state if the config is set

        Listens to: sensor/setpoint
        Next states: ready

        Args:
            topic: str: The topic of the message
            msg: str: The message

        Returns:
            None
        """

        if topic.decode("utf-8") == f"sensor/setpoint":
            params = ujson.loads(msg)
            self.status["setpoint"] = params[self.config['SENSOR_ID']]
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

    def _apply_config(self, msg):
        params = ujson.loads(msg)
        self.status["config"]["p"] = params["p"]
        self.status["config"]["i"] = params["i"]
        self.status["config"]["d"] = params["d"]
        self.status["config"]["tolerance"] = params["tolerance"]
