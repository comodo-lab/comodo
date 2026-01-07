import time as t

from src.controller_helper import *
from utils import mqtt_clients as mqtt

config = json.load(open("config/config.json"))
sensor_setup_wait = config["sensor_setup_wait"]
timer_check_frequency = 0.1


def on_timer_message(client, msg, obj):
    """
    Callback function for the timer MQTT client.
    The timer client is used to de-couple the waiting times that the controller needs to wait,
    but keeps the controller callback available, as opposed to using time.sleep() in the controller,
    which would block the callback.
    The timer client is used to wait for the sensors to be ready before starting the experiment,
    and to wait for the setpoint duration before moving to the next setpoint.
    """
    try:
        message = mqtt.load_message(msg)
        if message["uid"] != obj.experiment_uid:
            incompatible_uid(obj, msg, source="timer")
            return
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e, source="timer")
        return

    if msg.topic == "timer/start/sensor_setup":
        # Wait for sensors to be ready or timeout
        t0 = t.time()
        while (not obj.sensors["configured"]) and obj.status == "awaiting_sensors":
            t.sleep(timer_check_frequency)
            if t.time() - t0 > sensor_setup_wait:
                controller_timeout(message["uid"], "sensors", "Stopping")
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/stop", json.dumps({"uid": message["uid"]})
                )
                return
        mqtt.MQTTPublisher.get_instance().publish(
            "timer/done/sensor_setup",
            json.dumps(
                {
                    # experiment uid changes when all sensors get configured, so have to use obj.experiment_uid, not message["uid"]
                    "uid": obj.experiment_uid,
                    "sensors_configured": obj.sensors["configured"],
                    "controller_status": obj.status,
                }
            ),
        )
    elif msg.topic == "timer/start/setpoint":
        try:
            duration = message["duration"]
        except KeyError as e:
            missing_keys(msg, e, source="timer")
            return
        # Start timer for setpoint
        t0 = t.time()
        while obj.status == "running":
            t.sleep(timer_check_frequency)
            if t.time() - t0 > duration:
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/run",
                    json.dumps({"uid": message["uid"]}),
                )
                return
        if obj.status != "stopping":
            controller_state_incompatible_with_timer(
                message["uid"], "setpoint", "running", obj.status
            )
        else:
            mqtt.MQTTPublisher.get_instance().publish(
                "timer/done/setpoint",
                json.dumps({"uid": message["uid"], "controller_status": obj.status}),
            )
    elif msg.topic.startswith("timer/done/"):
        return
    else:
        incompatible_request(obj, msg, source="timer")
