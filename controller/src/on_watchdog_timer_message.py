import time as t
from controller_helper import *
from error_helper import *


def on_wd_timer_message(client, msg, obj):
    """
    Callback function for the watchdog timer.
    This timer should be always running and occupied, so it needs to be separate from the other timers.
    It is kept alive by the watchdog, which resets the value of the timer every time a heartbeat is received.
    """
    try:
        message = load_message(msg)
    except json.JSONDecodeError as e:
        wrong_json(msg, e, source="wd_timer")
        if msg.topic == "wd_timer/start":
            print("ERROR: Watchdog timer failed to start.")
            print(f"  Wrong json: {e}")
        return

    if msg.topic == "wd_timer/start":
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
            MQTTPublisher.get_instance().publish(
                "error/wd_timer",
                json.dumps({"error": error}),
            )
            print("ERROR: Watchdog timer failed to start.")
            print(f"Values do not match: {e}")
            return
        except KeyError as e:
            missing_keys(msg, e, source="wd_timer")
            print("ERROR: Watchdog timer failed to start.")
            print(f"Missing keys: {e}")
            return
        # Start timer for watchdog
        obj["healthy"] = True
        print("  Watchdog running.")
        while obj["healthy"]:
            t.sleep(timer_interval)
            obj["timer"] = obj["timer"] - timer_interval
            if obj["timer"] <= 0:
                MQTTPublisher.get_instance().publish(
                    "watchdog/timeout",
                    json.dumps(
                        {
                            "error": f'No heartbeat received in {obj["timeout"]} seconds. Expected every {obj["interval"]}s.'
                        }
                    ),
                )
                return
    else:
        error = f"WATCHDOG_TIMER: Unexpected message received: {msg.topic}"
        MQTTPublisher.get_instance().publish(
            "error/wd_timer",
            json.dumps({"error": error}),
        )
