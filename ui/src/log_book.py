"""
Keeps a log of the latest error messages published on error/# over MQTT, along with
the experiment lifecycle messages, so the Dash callbacks can show them without access
to the container logs.
"""

import json
import threading
import time
from collections import deque

from utils.mqtt_clients import MQTTClient

ERROR_TOPIC = "error/#"
# Lifecycle messages logged as events, with how to describe them from their payload
EVENT_TOPICS = {
    "ui/start": lambda p: f"Experiment {p.get('temp_id')} requested.",
    "controller/command/start": lambda p: (
        f"Experiment {p.get('experiment_id')} starting."
    ),
    "controller/command/stop": lambda p: (
        f"Stopping experiment {p.get('experiment_id')}."
    ),
    "controller/command/reset": lambda p: (
        f"Instruments and setpoint controllers reset by the {p.get('source', 'unknown')}."
    ),
}
MAX_ENTRIES = 500  # Oldest entries are dropped once the log is full

# Global state of the messages received over MQTT. The Dash callbacks read this state.
_counter = 0  # Increases with every entry, used to check when something arrived
_errors = 0  # Increases with every error, used to count the errors not yet seen
_entries = deque(maxlen=MAX_ENTRIES)  # Oldest first
_lock = threading.Lock()


def on_message(client, msg, obj):
    """
    Adds the error or lifecycle event to the log. Payloads that are not valid JSON
    objects are kept as raw text, so nothing published on error/# is lost.
    """
    global _counter, _errors
    raw = msg.payload.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        payload = {"code": "unknown", "message": raw}

    if msg.topic in EVENT_TOPICS:
        entry = {
            "type": "event",
            "source": msg.topic.split("/", 1)[0],
            "code": msg.topic,
            "message": EVENT_TOPICS[msg.topic](payload),
        }
    else:
        entry = {
            "type": "error",
            "source": msg.topic.split("/", 1)[-1],
            "code": str(payload.get("code", "unknown")),
            "message": str(payload.get("message", raw)),
        }

    with _lock:
        _counter += 1
        if entry["type"] == "error":
            _errors += 1
        _entries.append({"id": _counter, "received": time.time(), **entry})


def snapshot():
    """
    Returns the counters and the logged entries, newest first.
    """
    with _lock:
        return {
            "counter": _counter,
            "errors": _errors,
            "entries": list(reversed(_entries)),
        }


def start(id, **mqtt_kwargs):
    """
    Subscribes to the errors published by any component and the lifecycle messages.
    """
    topics = [ERROR_TOPIC, *EVENT_TOPICS]
    MQTTClient(id=id, callback=on_message, topics=topics, **mqtt_kwargs)
