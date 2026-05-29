# System imports
import os
import sys
from pathlib import Path

import traceback
import asyncio

# Shared utils imports
from utils import mqtt_clients as mqtt

# Local imports
import checks
from utils import message_spec

def on_message(client, msg, topic_map):
    # Get the entry from the spec
    entry = topic_map.get(msg.topic)
    payload = msg.payload
    topic = msg.topic
    
    # Check that the topic is in the register defined by the AsyncAPI spec
    if not checks.check_topic_expected(entry, topic):
        return

    # Check the validity of the JSON payload
    if not checks.check_payload_json_validity(topic, payload):
        return

    # Perform message validation against the AsyncAPI schemea
    if not checks.check_message_valid(entry, topic, payload):
        return

async def main():
    # Initialise the MQTTPublisher singleton 
    mqtt.MQTTPublisher.get_instance(
        id="publisher-monitor",
        broker_address=os.getenv("MQTT_HOST", "localhost"),
        user=os.getenv("MQTT_USER", "guest"),
        password=os.getenv("MQTT_PASS", "guest"),
        connection_timeout=60,
    )

    # Load the AsyncAPI specification 
    topic_map = message_spec.load_spec()

    # Create the MQTT client for subscription
    client = mqtt.MQTTClient(
        id='mqtt-monitor',
        callback=on_message,
        topics=['#'],
        broker_address=os.getenv("MQTT_HOST", "localhost"),
        user=os.getenv("MQTT_USER", "guest"),
        password=os.getenv("MQTT_PASS", "guest"),
        connection_timeout=60,
        obj=topic_map
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
            state.client.publish(
                f"error/monitor", str(e)
            )
        except:
            print(f"Error: {e}")
