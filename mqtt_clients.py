import paho.mqtt.client as mqtt
import time as t
from datetime import datetime
from json import dumps, loads


def print_message(client, msg, timestamped=False):
    """
    Print the message received from the MQTT client to the console in the format:
    <client id>: <topic>: <message>
    or if timestamped=True:
    <time> - <client id>: <topic>: <message>

    Parameters:
    - client: The MQTT client object.
    - msg: The message received from the MQTT client.
    - timestamped: If True, includes the timestamp in the printed message. Defaults to False.

    Returns:
    None
    """
    m = msg.payload.decode("utf-8")
    t = ""
    if timestamped:
        t = f"{datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')} - "
    print(f"{t}{client.id}: " + f"{msg.topic}: {m}")


def on_client_message(client, msg, obj):
    """
    Default callback when a message is received from an MQTT client.
    The message is printed to the console in the format:
    <client id>: <topic>: <message>
    """
    print_message(client, msg)


class MQTTClient:
    """
    A class representing an MQTT client.

    Args:
        id (str, optional): The client ID. Defaults to "client".
        callback (function, optional): The callback function to be called when a message is received. Defaults to on_client_message.
        topics (str, optional): The MQTT topics to subscribe to. Defaults to "/#".
        broker_address (str, optional): The address of the MQTT broker. Defaults to "localhost".
        port (int, optional): The port number of the MQTT broker. Defaults to 1883.
        user (str, optional): The username for authentication. Defaults to None.
        password (str, optional): The password for authentication. Defaults to None.
        start_loop (bool, optional): Whether to start the MQTT client loop. Defaults to True.
        obj (object, optional): An additional object to be passed to the callback function. Defaults to None.
    """

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
        """
        Provides a publish method for the MQTTClient object,
        which calls the publish method of the underlying MQTT client.
        """
        self.client.publish(topic, msg)
