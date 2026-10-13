"""
Keeps a log of the latest error messages published on error/# over MQTT,
so the Dash callbacks can show them without access to the container logs.
"""

import json
import threading
import time
from collections import deque

from utils.mqtt_clients import MQTTClient

ERROR_TOPIC = "error/#"
MAX_ENTRIES = 500  # Oldest entries are dropped once the log is full

# Global state of the errors received over MQTT. The Dash callbacks read this state.
_counter = 0  # Increases with every error, used to check when something arrived
_entries = deque(maxlen=MAX_ENTRIES)  # Oldest first
_lock = threading.Lock()


def on_error(client, msg, obj):
    """
    Adds the error to the log. Errors that are not valid JSON are kept as raw text,
    so nothing published on error/# is lost.
    """
    global _counter
    raw = msg.payload.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        payload = {"code": "unknown", "message": raw}

    with _lock:
        _counter += 1
        _entries.append(
            {
                "id": _counter,
                "received": time.time(),
                "source": msg.topic.split("/", 1)[-1],
                "code": str(payload.get("code", "unknown")),
                "message": str(payload.get("message", raw)),
            }
        )


def snapshot():
    """
    Returns the counter and the logged errors, newest first.
    """
    with _lock:
        return {"counter": _counter, "entries": list(reversed(_entries))}


def start(id, **mqtt_kwargs):
    """
    Subscribes to the errors published by any component.
    """
    MQTTClient(id=id, callback=on_error, topics=ERROR_TOPIC, **mqtt_kwargs)
