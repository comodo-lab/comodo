from lib.simple import MQTTClient
import time as t

from machine import Timer

# Setup mqtt client
c = MQTTClient("umqtt_client",
               "192.168.1.246",
               port=1883,
               user="sensor",
               password="foobar!!")
c.connect()

count = 0
while True:
    temp = count
    count += 1
    c.publish(b"/sensor/rpi-tc/temperature",str(temp))
    t.sleep(1)
