import lib.unittest as unittest
import lib.umqtt as mqtt
import time as t

import sys
import main as main

class MQTTTest(unittest.TestCase):
    def setUp(self):
        self.config = main.load_config()
    
    def test_Client_CorrectIP(self):
        self.client = mqtt.MQTTClient("umqtt_client",
                                      self.config["MQTT_IP"],
                                      port=1883,
                                      user="sensor",
                                      password="foobar!!")
        connected = self.client.connect()
        self.assertIs(connected, 0)

    # def test_Client_IncorrectIP(self):
    #     self.client = mqtt.MQTTClient("umqtt_client",
    #                                   "1.2.3.4",
    #                                   port=1883,
    #                                   user="sensor",
    #                                   password="foobar!!")
    #     connected = self.client.connect()
    #     self.assertIs(connected, 113)

    def tearDown(self):
        self.client.disconnect()
