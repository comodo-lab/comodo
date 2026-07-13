import time as t
import json

from utils import mqtt_clients as mqtt

from src.error_helper import (
    incompatible_topic,
    wrong_json,
    missing_keys,
)


def on_wd_timer_message(client, msg, obj):
    """
    Callback function for the watchdog timer.
    This timer should be always running and occupied, so it needs to be separate from the other timers.
    It is kept alive by the watchdog, which resets the value of the timer every time a heartbeat is received.
    """
    try:
        message = mqtt.load_message(msg)
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        if msg.topic == "watchdog/timer/command/start":
            print("ERROR: Watchdog timer failed to start.")
            print(f"  Wrong json: {e}")
            obj["healthy"] = False
        return

    if msg.topic == "watchdog/timer/command/start":
        try:
            assert (
                message["timeout"] == obj["timeout"]
            ), f"Expected timeout {obj['timeout']}, but got {message['timeout']}"
            assert (
                message["interval"] == obj["interval"]
            ), f"Expected interval {obj['interval']}, but got {message['interval']}"
            obj["timer"] = obj["timeout"]
            timer_interval = 0.6 * obj["interval"]
        except AssertionError as e:
            error = f"WATCHDOG_TIMER incompatible values: {e}"
            mqtt.MQTTPublisher.get_instance().publish(
                "error/watchdog_timer",
                json.dumps({"code": "incompatible_values", "message": error}),
            )
            print("ERROR: Watchdog timer failed to start.")
            print(f"Values do not match: {e}")
            obj["healthy"] = False
            return
        except KeyError as e:
            missing_keys(msg, e)
            print("ERROR: Watchdog timer failed to start.")
            print(f"Missing keys: {e}")
            obj["healthy"] = False
            return
        # Start timer for watchdog
        obj["healthy"] = True
        print("  Watchdog running.")
        while obj["healthy"]:
            t.sleep(timer_interval)
            obj["timer"] = obj["timer"] - timer_interval
            if obj["timer"] <= 0:
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
        incompatible_topic(obj, msg, "watchdog_timer")
