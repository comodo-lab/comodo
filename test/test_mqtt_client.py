import lib.unittest as unittest
import lib.umqtt as mqtt
from machine import WDT

class MQTTTest(unittest.TestCase):
    def test_ClientConnected(self):
        client = mqtt.MQTTClient("umqtt_client",
                                 "0.0.0.1",
                                 port=1883,
                                 user="sensor",
                                 password="foobar!!")
        connected = client.connect()
        print("")
        print("----------------------")
        print(connected)
        print(type(connected))

        self.assertIs(connected, 0)

    # def test_ClientNotConnected(self):
    #     client = mqtt.MQTTClient("umqtt_client",
    #                              "1.2.3.4",
    #                              port=1883,
    #                              user="sensor",
    #                              password="foobar!!")

    #     self.assertRaises("OSError",func=client.connect)

    
