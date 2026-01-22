import sys
import os

import time as t
import json
import textwrap

from utils import mqtt_clients as mqtt

from src.controller_helper import get_env_or_secret
from src.controller_state import cstate
from src.on_watchdog_message import on_watchdog_message
from src.on_watchdog_timer_message import on_wd_timer_message
from src.on_ui_message import on_ui_message
from src.on_controller_message import c_idle
from src.on_timer_message import on_timer_message
from src.on_heartbeat_message import on_heartbeat_message


def main():
    print(f"Starting...")
    # Load configuration
    expected_env_vars = [
        ["MQTT_HOST"],
        ["MQTT_USER"],
        ["MQTT_PASS", "MQTT_PASS_FILE"],
        ["MQTT_CONNECTION_TIMEOUT"],
        ["WATCHDOG_INTERVAL"],
        ["WATCHDOG_TIMEOUT"],
        ["INFLUX_BUCKET"],
        ["INFLUX_ADDR"],
        ["INFLUX_ORG"],
        ["INFLUX_TOKEN", "INFLUX_TOKEN_FILE"],
        ["SENSOR_SETUP_WAIT"],
    ]
    env_vars = list(os.environ.keys())

    for var_group in expected_env_vars:
        if not any(var in env_vars for var in var_group):
            print(
                f"WARNING: environment variables not set for: {', '.join(var_group)}."
            )

    mqtt_host = os.getenv("MQTT_HOST", "rabbitmq")
    mqtt_user = os.getenv("MQTT_USER", None)
    mqtt_pass = get_env_or_secret("MQTT_PASS", "MQTT_PASS_FILE", None)
    connection_timeout = os.getenv("MQTT_CONNECTION_TIMEOUT", 10)
    wdog_interval = os.getenv("WATCHDOG_INTERVAL", 1)
    wdog_timeout = os.getenv("WATCHDOG_TIMEOUT", 5)

    assert wdog_interval > 0
    assert wdog_timeout > 2 * wdog_interval
    wdog = {
        "interval": wdog_interval,
        "timeout": wdog_timeout,
        "timer": wdog_timeout,
        "healthy": False,
    }

    # Initialize controller state
    state = cstate()

    print(f"  Creating clients...")

    # Initialise publisher singleton
    publisher = mqtt.MQTTPublisher.get_instance(
        id="publisher_controller",
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )

    # Load MQTT clients
    watchdog = mqtt.MQTTClient(
        id="watchdog",
        callback=on_watchdog_message,
        topics=["watchdog/#", "heartbeat/controller", "ERROR/exception"],
        obj=wdog,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    wd_timer = mqtt.MQTTClient(
        id="wd_timer",
        callback=on_wd_timer_message,
        topics="wd_timer/#",
        obj=wdog,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    ui = mqtt.MQTTClient(
        id="ui",
        callback=on_ui_message,
        topics="ui/#",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    controller = mqtt.MQTTClient(
        id="controller",
        callback=c_idle,
        topics="controller/#",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    timer = mqtt.MQTTClient(
        id="timer",
        callback=on_timer_message,
        topics="timer/#",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    heartbeat = mqtt.MQTTClient(
        id="heartbeat",
        callback=on_heartbeat_message,
        topics="heartbeat/sensor/#",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    # measurement = mqtt.MQTTClient("measurement", on_client_message, topics="measurement/#")

    publisher.client.publish("wd_timer/start", json.dumps(wdog))
    t.sleep(1)
    if wdog["healthy"]:
        print(f"Controller started successfully.")
    else:
        print(f"Controller failed to start. watchdog unhealthy.")
    while wdog["healthy"]:
        controller.publish("heartbeat/controller", f"{state}")
        t.sleep(wdog["interval"])

    print(f"Exiting...")


if __name__ == "__main__":
    main()  # pragma: no cover
