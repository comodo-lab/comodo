import paho.mqtt.client as mqtt
import time as t
from datetime import datetime
from json import dumps, loads


def print_message(client, msg, type="time"):
    m = msg.payload.decode("utf-8")
    if type != "raw":
        try:
            m = loads(m)
            if type == "time":
                m = f"{m['timestamp'].split(' ')[1]} {dumps(m['msg'])}"
            elif type == "msg":
                m = m["msg"]
        except:
            pass
    print(f"{client.id}: " + f"{msg.topic}: {m}")


def on_client_message(client, msg, obj):
    print_message(client, msg, type="time")


class MQTTClient:
    def __init__(
        self,
        id="client",
        callback=on_client_message,
        topics="/#",
        broker_address="localhost",
        port=1883,
        user=None,
        password=None,
        start_loop=True,
        obj=None,
    ):
        self.id = id
        self.client = mqtt.Client(id)
        self.obj = obj
        self.client.on_message = lambda client, userdata, msg: callback(
            self, msg, self.obj
        )
        if user is not None:
            self.client.username_pw_set(username=user, password=password)
        self.client.connect(broker_address, port, 60)
        self.client.subscribe(topics, 0)
        if start_loop:
            self.client.loop_start()

    def publish(self, topic, msg):
        timestamp = datetime.fromtimestamp(t.time()).strftime("%Y-%m-%d %H:%M:%S")
        try:
            msg = loads(msg)
        except:
            pass
        payload = {
            "timestamp": timestamp,
            "msg": msg,
        }
        self.client.publish(topic, dumps(payload))
