import lib.unittest as unittest
import lib.umqtt as mqtt
import time as t

import sys
import config as cfg
import connect as con

class MQTTTest(unittest.TestCase):
    def setUp(self):
        self.config = cfg.load_config()
        self.client = None
    
    def test_Client_CorrectIP(self):
        connection = con.connect_wifi(self.config["WIFI_SSID"], self.config["WIFI_PASS"])
        print(connection)
        self.client = con.connect_mqtt("umqtt_client_test",
                                       self.config["MQTT_IP"],
                                       port=1883,
                                       user="sensor",
                                       password="foobar!!")
        connected = self.client.connect()
        self.assertIs(connected, 0)

    def test_test(self):
        with self.assertRaises(Exception): 
            1 + '1'


    def test_Client_IncorrectIP(self):
        connection = con.connect_wifi(self.config["WIFI_SSID"], self.config["WIFI_PASS"])
        print(connection)
        with self.assertRaises(Exception) as context:
            con.connect_mqtt("umqtt_client_test",
                             "1.2.3.4",
                             port=1883,
                             user="sensor",
                             password="foobar!!")
            print(context.exception)
            self.assertTrue('Timeout connecting to the mqtt broker' in context.exception)

            
    def tearDown(self):
        if self.client is not None:
            self.client.disconnect()
