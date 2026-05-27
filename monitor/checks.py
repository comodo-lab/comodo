def check_payload_json_validity(client, topic):
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError as e:
        self.publish_error(
            client,
            "error/message/validation",
            {
                "topic": topic,
                "error": "invalid_json",
                "message": str(e),
            }
        )

def check_topic_expected(client, topic):
    if entry is None:
        self.publish_error(
            client,
            "error/message/unexpected",
            {
                "topic": topic,
                "error": "unexpected_topic",
                "payload": payload,
            }
        )

def check_message_valid(client, topic):
    try:
        validate(payload, entry["schema"])
    except ValidationError as e:
        self.publish_error(
            client
            "error/validation",
            {
                "topic": topic,
                "channel": entry["name"],
                "error": "validation_error",
                "path": list(e.absolute_path) if e.absolute_path else None,
                "message": e.message,
            }
        )
        
def publish_error(client, topic, data):
    self.client.publish(topic, json.dumps(data))
    print(f"  published {topic}: {data.get('error')}")

