import paho.mqtt.client as mqtt
import time as t
import json


def on_ui_message(client, msg, obj):
    print_message(client, msg)
    experiment = msg.payload.decode("utf-8")
    experiment = json.loads(experiment)
    if obj.running == "idle":
        if msg.topic == "/ui/start":
            obj.experiment = experiment["uid"]
            client.publish("/received/ui", f"Received experiment: {obj.experiment}")
            with open(f"data/experiment_{obj.experiment}.json", "w") as f:
                json.dump(experiment, f)
            obj.running = "starting"
    else:
        if msg.topic == "/ui/stop":
            if experiment["uid"] == obj.experiment:
                obj.running = "stopping"
                client.publish(
                    "/received/ui",
                    f"Received stop command for experiment {obj.experiment}",
                )
            else:
                client.publish(
                    "/error/ui",
                    f"Experiment {obj.experiment} is {obj.running}. Cannot act on {msg.topic} for experiment {experiment['uid']}",
                )
        else:
            client.publish(
                "/error/ui",
                f"Experiment {obj.experiment} is {obj.running}. Cannot act on {msg.topic}",
            )


def on_heartbeat_message(client, msg, obj):
    print_message(client, msg)


def on_measurement_message(client, msg, obj):
    print_message(client, msg)


def on_controller_message(client, msg, obj):
    print_message(client, msg)


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
        start_loop=True,
        obj=None,
    ):
        self.client = mqtt.Client(id)
        self.obj = obj
        self.client.on_message = lambda client, userdata, msg: callback(
            client, msg, self.obj
        )
        self.client.connect(broker_address, port, 60)
        self.client.subscribe(topics, 0)
        if start_loop:
            self.client.loop_start()

    def publish(self, topic, payload):
        self.client.publish(topic, payload)
