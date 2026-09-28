"""
Keeps the latest heartbeat of the controller, instruments and setpoint controllers,
received over MQTT, so the Dash callbacks can read them without querying InfluxDB.
"""

import json
import threading
import time

from utils.mqtt_clients import MQTTClient

CONTROLLER_TOPIC = "controller/heartbeat"
# Global state of the heartbeats received over MQTT. The Dash callbacks read this state.
_timeout = None  # Set as heartbeat_interval*2 when start() is called
_sources = []  # Instruments and setpoint controllers expected to send heartbeats
_counter = 0  # Increases with every heartbeat, used to check when something arrived
_latest = {}  # topic -> {"payload": dict, "received": epoch seconds}
_lock = threading.Lock()


def instrument_topic(name):
    return f"instruments/{name}/heartbeat"


def spc_topic(spc_id):
    return f"setpoint_controller/{spc_id}/heartbeat"


def get_sources(config):
    """
    Returns the heartbeat sources of the instruments and setpoint controllers in the
    ComodoConfig, as a list of {"topic", "label", "kind"} in config order.
    """
    sources = [
        {"topic": instrument_topic(name), "label": name, "kind": "instrument"}
        for name in config.instruments
    ]
    sources += [
        {
            "topic": spc_topic(spc_id),
            "label": f"{spc['external_sensor']} → {spc['actuator']}",
            "kind": "spc",
        }
        for spc_id, spc in config.spcs.items()
    ]
    return sources


def on_heartbeat(client, msg, obj):
    global _counter
    try:
        payload = json.loads(msg.payload)
    except ValueError as e:
        print(f"Invalid heartbeat on {msg.topic}: {e}")
        return
    with _lock:
        _latest[msg.topic] = {"payload": payload, "received": time.time()}
        _counter += 1


def snapshot(now=None):
    """
    Returns the expected sources, the latest heartbeats, the counter and the topics that have gone quiet.
    """
    now = now or time.time()
    with _lock:
        latest = dict(_latest)
        counter = _counter
    stale = sorted(t for t, hb in latest.items() if now - hb["received"] > _timeout)
    return {
        "sources": list(_sources),
        "counter": counter,
        "heartbeats": latest,
        "stale": stale,
    }


def start(config, id, **mqtt_kwargs):
    """
    Subscribes to the heartbeats of the controller, instruments and
    setpoint controllers in the ComodoConfig.
    """
    global _timeout, _sources
    _timeout = config.globals["heartbeat_interval"] * 2
    _sources = get_sources(config)
    topics = [s["topic"] for s in _sources]
    topics.append(CONTROLLER_TOPIC)
    MQTTClient(id=id, callback=on_heartbeat, topics=topics, **mqtt_kwargs)
