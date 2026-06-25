# System imports
import json
import os

import traceback
import asyncio
from jsonschema import ValidationError

# Shared utils imports
from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, MQTTValidationException


def on_message(client, msg, obj):
    try:
        validate_message(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
    except MQTTValidationException as e:
        mqtt.MQTTPublisher.get_instance().publish(
            "error/message",
            json.dumps(
                {
                    "code": "unexpected_topic",
                    "message": f"Unexpected topic: {msg.topic}",
                }
            ),
        )
    except json.JSONDecodeError as e:
        mqtt.MQTTPublisher.get_instance().publish(
            "error/message",
            json.dumps(
                {
                    "code": "invalid_json",
                    "message": str(e),
                    "topic": msg.topic,
                }
            ),
        )
    except ValidationError as e:
        offending_key = (
            ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "<root>"
        )
        mqtt.MQTTPublisher.get_instance().publish(
            "error/message",
            json.dumps(
                {
                    "code": "validation_error",
                    "message": e.message,
                    "topic": msg.topic,
                    "failed_check": e.validator,
                    "offending_key": offending_key,
                }
            ),
        )
    except Exception as error:
        print(f"ERROR: Message invalid: {error}")


async def main():
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        traceback.print_exc()
        try:
            mqtt.MQTTPublisher.get_instance().publish(
                "error/monitor", json.dumps({"code": "exception", "message": str(e)})
            )
        except:
            print(f"Error: {e}")
