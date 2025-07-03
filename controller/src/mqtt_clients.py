from typing import Any, Callable, Optional, List, Union
import paho.mqtt.client as mqtt
from datetime import datetime
import json
import os
import time as t
import threading

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
    print_message(client, msg, timestamped=True)


def mqtt_publish_exceptions(name, func):
    """
    A decorator to catch unhandled exceptions in the callback functions of the MQTT clients.
    It publishes the exception message to the "ERROR/exception" topic.
    It also prints the exception and traceback to the console.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"ERROR:\n   Unhandled exception in {name}: {str(e)}")
            # print all e.__traceback__.tb_frame and recurring tb_next
            print(f"Traceback:")
            tb = e.__traceback__
            indent = "   "
            while tb is not None:
                frame = tb.tb_frame
                filename = frame.f_code.co_filename
                base_folder = os.path.dirname(os.path.abspath(__file__))
                relative_filename = os.path.relpath(filename, base_folder)
                function_name = frame.f_code.co_name
                line_number = frame.f_lineno
                print(
                    f"{indent}< file: '{relative_filename}', function: '{function_name}', line: {line_number} >"
                )
                indent += " "
                tb = tb.tb_next

            try:
                MQTTPublisher.get_instance().publish(
                    "ERROR/exception",
                    json.dumps({"error": f"Unhandled exception in {name}: {str(e)}"}),
                )
            except Exception as e:
                print(f"Error while reporting error! {e}")

    return wrapper


def on_connect(client, userdata, flags, rc, properties):
    id = userdata.get("id")
    
    # Check connection was ok
    if rc != 0:
        raise TimeoutError("{id} client failed to connect.")
    else:
        print(f"Client {id} successfully connected to broker.")
    
    # Selectively subscribe to topics
    topics = userdata.get("topics")

    # Convert to list if needed
    if isinstance(topics, str):
        topics = [topics]
        
    if isinstance(topics, list):
        for topic in topics:
            result, mid = client.subscribe(topic, 0)
            if result == mqtt.MQTT_ERR_SUCCESS:
                print(f"           '{id}' subscribed to '{topic}'.")
            else:
                print(
                    f"           '{id}' failed to subscribe to '{topic}' with error code: {result}"
                )

class MQTTClient:
    """
    A class to simplify the process of creating and setting up MQTT clients.
    It encapsulates the MQTT client configuration and provides a simple interface for interacting with an MQTT broker.
    """

    def __init__(
        self,
        id: str = "client",
        callback: Callable = on_client_message,
        topics: Union[str, List[str]] = "#",
        broker_address: str = "localhost",
        port: int = 1883,
        user: Optional[str] = None,
        password: Optional[str] = None,
        connection_timeout: int = 60,
        obj: Optional[Any] = None,
    ):
        """
        Initialization of MQTTClient objects.

        Args:
        id: The client ID. Defaults to "client".
        callback: The callback function to be called when a message is received. Defaults to on_client_message.
        topics: The MQTT topics to subscribe to. Defaults to "#".
        broker_address: The address of the MQTT broker. Defaults to "localhost".
        port: The port number of the MQTT broker. Defaults to 1883.
        user: The username for authentication. Defaults to None.
        password: The password for authentication. Defaults to None.
        connection_timeout: The time to wait for making a connection. Defaults to indefinite (0)
        obj: An additional object to be passed to the callback function. This would normally be the controller state object. Defaults to None.
        """
        self.id = id
        # ----------------------------------------------------------------------
        # Create client and register a callback which will perform subscriptions
        
        self.client = mqtt.Client(client_id=id,
                                  callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                  userdata={"topics": topics},
                                  )
        self.client.on_connect = on_connect
        
        self.obj = obj
        self.callback = callback
        if user is not None:
            self.client.username_pw_set(username=user, password=password)
        # try:
        #     self.client.connect(broker_address, port, 60)
        # except Exception as e:
        #     print(f"ERROR: Client '{id}' failed to connect to broker: {e}")
        #     raise e
        self.client.connect(broker_address, port, connection_timeout)
        self.client.loop_start()
        #connect_or_timeout(self, connection_timeout)

    def publish(self, topic, msg):
        """
        Provides a publish method for the MQTTClient object,
        which calls the publish method of the underlying MQTT client.
        """
        self.client.publish(topic, msg)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, callback):
        """
        Sets the callback function for the MQTT client.
        The on_message is wrapped with the mqtt_publish_exceptions decorator to publish unhandled exceptions.
        The controller client uses this to reflect its different states.
        """
        self._callback = callback
        if callback is not None:
            self.client.on_message = mqtt_publish_exceptions(
                callback.__name__,
                lambda client, userdata, msg: callback(self, msg, self.obj),
            )


def load_message(msg):
    """
    Decodes and loads the message received from the MQTT client as a JSON object.
    Exceptions need to be caught when calling this function.
    """
    return json.loads(msg.payload.decode("utf-8"))


class MQTTPublisher:
    """
    A thread-safe singleton class for publishing MQTT messages.
    
    This class provides a central object for message publishing, shared throughout
    the application. It implements the singleton pattern to ensure only one
    publisher instance exists.
    
    Usage:
        # First initialization with connection parameters
        publisher = MQTTPublisher.get_instance(
            broker_address="foo.example.com",
            port=1883,
            user="username",
            password="password"
        )
        
        # Later usage from anywhere in the application
        publisher = MQTTPublisher.get_instance()
        publisher.publish("topic/subtopic", "message payload")
    
    Note:
        The instance must be initialized with parameters on first call to get_instance().
        Subsequent calls can omit parameters and will return the existing instance.
    """
    _instance = None

    def __init__(
            self,
            id: str = "publisher",
            broker_address: str = "localhost",
            port: int = 1883,
            user: Optional[str] = None,
            password: Optional[str] = None,
            connection_timeout: int = 0,
    ):
        self.client = MQTTClient(
            id=id,
            topics=None,
            callback=None,
            broker_address=broker_address,
            port=port,
            user=user,
            password=password,
            connection_timeout=connection_timeout,
        )
        self._lock = threading.Lock()
        
    def publish(self, topic: str, payload: str):
        with self._lock:
            try:
                self.client.publish(topic, payload)
            except Exception as e:
                print(f"Error publishing message {e}")

    @classmethod
    def get_instance(cls, **kwargs):
        if cls._instance is None:
            if not kwargs:
                raise RuntimeError("MQTTPublisher not yet initialised; call get_instance(...) with parameters first")
            cls._instance = cls(**kwargs)
        elif cls._instance is not None and kwargs:
            print("MQTTPublisher already initialised; further parameters are ignored")

        return cls._instance
