import paho.mqtt.client as mqtt


def print_message(client, msg):
    print(
        f"{client._client_id.decode('utf-8')} :"
        + f"{msg.topic} : {msg.payload.decode('utf-8')}"
    )


def on_client_message(client, msg, obj):
    print_message(client, msg)


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
        self.client = mqtt.Client(id)
        self.obj = obj
        self.client.on_message = lambda client, userdata, msg: callback(
            client, msg, self.obj
        )
        if user is not None:
            self.client.username_pw_set(username=user, password=password)
        self.client.connect(broker_address, port, 60)
        self.client.subscribe(topics, 0)
        if start_loop:
            self.client.loop_start()

    def publish(self, topic, payload):
        self.client.publish(topic, payload)
