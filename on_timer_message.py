import time as t
from controller_helper import *

sensor_setup_wait = 10


def on_timer_message(client, msg, obj):
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
                pub.publish(
                    "error/controller/timeout",
                    json.dumps({"error": f"Timed out waiting for sensors. Exiting..."}),
                )
                pub.publish("controller/stop", json.dumps({"uid": message["uid"]}))
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
                pub.publish(
                    "controller/run",
                    json.dumps({"uid": message["uid"]}),
                )
                return
    else:
        incompatible_request(obj, msg, source="timer")
