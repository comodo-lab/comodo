import json

from utils import mqtt_clients as mqtt

from src.error_helper import wrong_json


def on_watchdog_message(client, msg, obj):
    """
    The watchdog makes sure that the controller is alive and healthy.
    It does so by listening to three topics:
    - heartbeat/controller: to check if the controller is alive
    - ERROR/exception: to check if the controller is healthy
    - watchdog/restart: to take action if needed
    Every heartbeat triggers a timer that, if not reset, will trigger an error.
    The watchdog can also be used to reset the controller.
    """
    try:
        message = mqtt.load_message(msg)
    except json.JSONDecodeError as e:
        wrong_json(msg, e, source="watchdog")
        return

    if msg.topic == "heartbeat/controller":
        obj["timer"] = obj["timeout"]
        return
    elif msg.topic == "ERROR/exception":
        # {"error": f"Unhandled exception in {name}: {str(e)}"}
        error = mqtt.load_message(msg)["error"]
        print(f"WATCHDOG: Received ERROR: {error}")
        mqtt.MQTTPublisher.get_instance().publish(
            "watchdog/restart", json.dumps({"message": "Restarting controller..."})
        )
        return
    elif msg.topic == "watchdog/timeout":
        error = mqtt.load_message(msg)["error"]
        print(f"WATCHDOG: Timed out waiting for controller heartbeat. {error}")
        mqtt.MQTTPublisher.get_instance().publish(
            "watchdog/restart", json.dumps({"message": "Restarting controller..."})
        )
        return
    elif msg.topic == "watchdog/restart":
        print("Restarting controller...")
        obj["healthy"] = False
        return
    else:
        error = f"WATCHDOG: Unexpected message received: {msg.topic}"
        mqtt.MQTTPublisher.get_instance().publish(
            "error/watchdog",
            json.dumps({"error": error}),
        )
