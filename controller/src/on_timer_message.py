import time as t

from src.controller_helper import *

config = json.load(open("config/config.json"))
sensor_setup_wait = config["sensor_setup_wait"]


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
        message = load_message(msg)
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
            t.sleep(0.1)
            if t.time() - t0 > sensor_setup_wait:
                controller_timeout(message["uid"], "sensors", "Stopping")
                MQTTPublisher.get_instance().publish(
                    "controller/stop", json.dumps({"uid": message["uid"]})
                )
                return
    elif msg.topic == "timer/start/setpoint":
        try:
            duration = message["duration"]
        except KeyError as e:
            missing_keys(msg, e, source="timer")
            return
        # Start timer for setpoint
        t0 = t.time()
        while obj.status == "running":
            t.sleep(0.1)
            if t.time() - t0 > duration:
                MQTTPublisher.get_instance().publish(
                    "controller/run",
                    json.dumps({"uid": message["uid"]}),
                )
                return
        if obj.status != "stopping":
            controller_state_incompatible_with_timer(
                message["uid"], "setpoint", "running", obj.status
            )
    else:
        incompatible_request(obj, msg, source="timer")
