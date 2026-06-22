import json

from utils import mqtt_clients as mqtt

from src.error_helper import wrong_json


def on_watchdog_message(client, msg, obj):
    """
    The watchdog makes sure that the controller is alive and healthy.
    It does so by listening to:
    - controller/heartbeat: to check if the controller is alive
    - error/exception: to check if the controller is healthy
    - watchdog/timer/event/+: to react to watchdog events (e.g. timeout)
    - watchdog/timer/command/+: to react to watchdog commands (e.g. restart)
    Every heartbeat triggers a timer that, if not reset, will trigger an error.
    """
    try:
        message = mqtt.load_message(msg)
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return

    if msg.topic == "controller/heartbeat":
        obj["timer"] = obj["timeout"]
        return

    if msg.topic == "error/exception":
        error = mqtt.load_message(msg)["error"]
        print(f"WATCHDOG: Received error: {error}")
        mqtt.MQTTPublisher.get_instance().publish(
            "watchdog/timer/event/restart_triggered",
            json.dumps({"message": "Restarting controller..."}),
        )
        obj["healthy"] = False
        return

    if msg.topic.startswith("watchdog/timer/event/"):
        if msg.topic == "watchdog/timer/event/timeout":
            error = mqtt.load_message(msg)["message"]
            print(f"WATCHDOG: Timed out waiting for controller heartbeat. {error}")
            mqtt.MQTTPublisher.get_instance().publish(
                "watchdog/timer/event/restart_triggered",
                json.dumps({"message": "Restarting controller..."}),
            )
            obj["healthy"] = False
        return

    if msg.topic.startswith("watchdog/timer/command/"):
        return
