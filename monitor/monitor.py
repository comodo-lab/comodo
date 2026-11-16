# System imports
import json
import os

import asyncio
from jsonschema import ValidationError

# Shared utils imports
from utils import mqtt_clients as mqtt
import utils.mqtt_validator as mqtt_val


def print_and_publish_error(code, message, **details):
    """Prints an error about an invalid message, and publishes it on error/message."""
    topic = f" (topic: {details['topic']})" if "topic" in details else ""
    print(f"ERROR: {message}{topic}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/message",
        json.dumps({"code": code, "message": message, **details}),
    )


def on_message(client, msg, obj):
    try:
        mqtt_val.validate_message(
            topic=msg.topic,
            payload=msg.payload,
            combine_exceptions=False,
        )
    except mqtt_val.MQTTValidationException:
        print_and_publish_error("unexpected_topic", f"Unexpected topic: {msg.topic}")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print_and_publish_error("invalid_json", str(e), topic=msg.topic)
    except ValidationError as e:
        offending_key = (
            ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "<root>"
        )
        print_and_publish_error(
            "validation_error",
            e.message,
            topic=msg.topic,
            failed_check=e.validator,
            offending_key=offending_key,
        )
    except Exception as e:
        message = f"Could not validate message on {msg.topic}: {e}"
        print(f"ERROR: {message}")
        mqtt.MQTTPublisher.get_instance().publish(
            "error/monitor", json.dumps({"code": "exception", "message": message})
        )
        # Not raised, as MQTTClient would publish it on error/exception, which restarts the controller.


async def monitor():
    # Initialise the MQTTPublisher singleton
    mqtt.MQTTPublisher.get_instance(
        id="publisher-monitor",
        broker_address=os.getenv("MQTT_HOST", "localhost"),
        user=os.getenv("MQTT_USER", "guest"),
        password=os.getenv("MQTT_PASS", "guest"),
        connection_timeout=60,
    )

    # Create the MQTT client for subscription
    client = mqtt.MQTTClient(
        id="mqtt-monitor",
        callback=on_message,
        topics=["#"],
        broker_address=os.getenv("MQTT_HOST", "localhost"),
        user=os.getenv("MQTT_USER", "guest"),
        password=os.getenv("MQTT_PASS", "guest"),
        connection_timeout=60,
    )

    # Keep running forever
    await asyncio.Event().wait()

    return 0


def main():
    try:
        asyncio.run(monitor())
    except Exception as e:
        try:
            mqtt.MQTTPublisher.get_instance().publish(
                "error/monitor", json.dumps({"code": "exception", "message": str(e)})
            )
        except Exception:
            print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()  # pragma: no cover
