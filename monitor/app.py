# System imports
import json
import os
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml
from jsonschema import validate, ValidationError

# Shared utils imports
from utils import mqtt_clients as mqtt

# Local imports
import checks 

def on_message(self, _client, msg, topic_map):
    # Get the entry from the spec
    entry = self.topic_map.get(topic)
    
    # Check the validity of the JSON payload
    checks.check_payload_json_validity(client, msg.topic)

    # Check that the topic is in the register defined by the AsyncAPI spec
    checks.check_topic_expected(client, msg.topic)

    # Perform message validation against the AsyncAPI schemea
    checks.check_message_valid(client, msg.topic)

def main():
    # Load the AsyncAPI specification 
    topic_map = load_spec()

    # Create the MQTT client
    client = mqtt.MQTTClient(
        id='mqtt-monitor',
        callback=on_message,
        topics=['#'],
        broker_address=os.getenv("MQTT_HOST"),
        user=os.getenv("MQTT_USER"),
        password=os.getenv("MQTT_PASS"),
        connection_timeout=60,
        obj=topic_map
    )   

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
