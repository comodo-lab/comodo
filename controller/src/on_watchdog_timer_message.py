import time as t
import json

from utils import mqtt_clients as mqtt

import src.publish_error as pe


def on_wd_timer_message(client, msg, obj):
    """
    Callback function for the watchdog timer.
    This timer should be always running and occupied, so it needs to be separate from the other timers.
    It is kept alive by the watchdog, which resets the value of the time_remaining every time a heartbeat is received.
    """
    if msg.topic == "watchdog/timer/command/start":
        try:
            obj["time_remaining"] = obj["timeout"]
            timer_interval = 0.6 * obj["interval"]
        except KeyError as e:
            pe.missing_keys(msg, e)
            print("ERROR: Watchdog timer failed to start.")
            obj["healthy"] = False
            return
        # Start timer for watchdog
        obj["healthy"] = True
        print("  Watchdog running.")
        while obj["healthy"]:
            t.sleep(timer_interval)
            obj["time_remaining"] -= timer_interval
            if obj["time_remaining"] <= 0:
                mqtt.MQTTPublisher.get_instance().publish(
                    "watchdog/timer/event/timeout",
                    json.dumps(
                        {
                            "error": f'No heartbeat received in {obj["timeout"]} seconds. Expected every {obj["interval"]}s.'
                        }
                    ),
                )
                return
    else:
        pe.incompatible_topic(obj, msg, "watchdog_timer")
