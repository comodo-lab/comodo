import paho.mqtt.client as mqtt
import time as t
import json

from validation import validate_experiment_soft


def on_ui_message(client, msg, obj):
    print_message(client, msg)
    experiment = msg.payload.decode("utf-8")
    experiment = json.loads(experiment)
    if obj.status == "idle":
        if msg.topic == "/ui/start":
            obj.experiment = experiment["uid"]
            # client.publish("/received/ui", f"Received experiment: {obj.experiment}")
            exp_file = f"data/experiment_{obj.experiment}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)
            obj.status = "validating"
            exp_config, err = validate_experiment_soft(exp_file, obj.schema_path)
            if err == None:
                m = {
                    "uid": obj.experiment,
                    "valid": True,
                }
                client.publish("/controller/validator/passed", json.dumps(m))
                obj.exp_config = exp_config
                obj.status = "starting"
            else:
                m = {
                    "uid": obj.experiment,
                    "valid": False,
                    "error": err,
                }
                client.publish("/controller/validator/failed", json.dumps(m))
                obj.experiment = None
                obj.status = "idle"
        else:
            client.publish(
                "/controller/error",
                f"Status is {obj.status}. Cannot act on {msg.topic}",
            )
    else:
        if msg.topic == "/ui/stop":
            if experiment["uid"] == obj.experiment:
                obj.status = "stopping"
                client.publish(
                    "/controller/stop",
                    f"Received stop command for experiment {obj.experiment}",
                )
            else:
                client.publish(
                    "/controller/error",
                    f"Experiment {obj.experiment} is {obj.status}. Cannot act on {msg.topic} for experiment {experiment['uid']}",
                )
        else:
            client.publish(
                "/controller/error",
                f"Experiment {obj.experiment} is {obj.status}. Cannot act on {msg.topic}",
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
