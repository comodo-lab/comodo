import json

from utils import mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val

import src.publish_error as pub_err


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
        message = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.message_validation(e)
        return

    if msg.topic == "controller/heartbeat":
        obj["time_remaining"] = obj["timeout"]
        return

    elif msg.topic == "error/exception":
        print(f"WATCHDOG: Received error: {message['message']}")
        mqtt.MQTTPublisher.get_instance().publish(
            "watchdog/timer/event/restart_triggered",
            json.dumps({"message": "Restarting controller..."}),
        )
        obj["healthy"] = False
        return

    elif msg.topic.startswith("watchdog/timer/event/"):
        if msg.topic == "watchdog/timer/event/timeout":
            error = message["message"]
            print(f"WATCHDOG: Timed out waiting for controller heartbeat. {error}")
            mqtt.MQTTPublisher.get_instance().publish(
                "watchdog/timer/event/restart_triggered",
                json.dumps({"message": "Restarting controller..."}),
            )
            obj["healthy"] = False
        return

    elif msg.topic.startswith("watchdog/timer/command/"):
        # Placeholder noop
        return

    else:
        pub_err.incompatible_topic(obj, msg, "watchdog")
