import time as t
from controller_helper import *


def on_timer_message(client, msg, obj):
    if msg.topic == "timer/start/sensor_setup":
        wait_for = 10
        message = load_message(msg)
        if message["uid"] == obj.experiment_uid:
            # Wait for sensors to be ready or timeout
            t0 = t.time()
            while (not obj.sensors["configured"]) and obj.status == "awaiting_sensors":
                t.sleep(0.1)
                if t.time() - t0 > wait_for:
                    pub.publish(
                        "error/controller",
                        f"Timed out waiting for sensors. Exiting...",
                    )
                    pub.publish("controller/stop", json.dumps({"uid": message["uid"]}))
                    return
    else:
        incompatible_request(obj, msg, source="timer")
