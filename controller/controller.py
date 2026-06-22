import sys
import os

import time as t
import json
import textwrap
import yaml

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
        ["INFLUX_BUCKET"],
        ["INFLUX_HOST"],
        ["INFLUX_ORG"],
        ["INFLUX_TOKEN", "INFLUX_TOKEN_FILE"],
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

    # Load comodo.yaml 
    try:
        with open("/app/comodo.yaml") as f:
            config = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError):
        config = {}

    global_config = config.get("global", {})

    wdog_interval = float(
        global_config.get("heartbeat", {}).get("interval", 1)
    )
    wdog_timeout = float(
        global_config.get("watchdog", {}).get("timeout", 5)
    )
    instrument_setup_wait = float(
        global_config.get("instrument_setup", {}).get("wait", -1)
    )
    assert instrument_setup_wait > 0, "instrument_setup.wait must be a positive number"

    assert wdog_interval > 0
    assert wdog_timeout > 2 * wdog_interval
    wdog = {
        "interval": wdog_interval,
        "timeout": wdog_timeout,
        "timer": wdog_timeout,
        "healthy": False,
    }

    # Compute actuator and sensor variables from instrument config
    actuator_variables = set()
    sensor_variables = set()
    for instr_name, instr_cfg in config.get("instruments", {}).items():
        for var_name, var_cfg in instr_cfg.get("variables", {}).items():
            if "actuator" in var_cfg:
                actuator_variables.add(f"{instr_name}/{var_name}")
            if "sensor" in var_cfg:
                sensor_variables.add(f"{instr_name}/{var_name}")

    # Initialize controller state
    state = cstate(instrument_setup_wait=instrument_setup_wait, actuator_variables=actuator_variables, sensor_variables=sensor_variables)

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
        topics=["watchdog/timer/event/+", "watchdog/timer/command/+", "controller/heartbeat", "error/exception"],
        obj=wdog,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    wd_timer = mqtt.MQTTClient(
        id="wd_timer",
        callback=on_wd_timer_message,
        topics="watchdog/timer/command/start",
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
        topics="controller/timer/#",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    heartbeat = mqtt.MQTTClient(
        id="heartbeat",
        callback=on_heartbeat_message,
        topics="instruments/+/heartbeat",
        obj=state,
        broker_address=mqtt_host,
        user=mqtt_user,
        password=mqtt_pass,
        connection_timeout=connection_timeout,
    )
    # measurement = mqtt.MQTTClient("measurement", on_client_message, topics="measurement/#")

    publisher.client.publish("watchdog/timer/command/start", json.dumps({"timeout": wdog["timeout"], "interval": wdog["interval"]}))
    t.sleep(1)
    if wdog["healthy"]:
        print(f"Controller started successfully.")
    else:
        print(f"Controller failed to start. watchdog unhealthy.")
    while wdog["healthy"]:
        controller.publish("controller/heartbeat", f"{state}")
        t.sleep(wdog["interval"])

    print(f"Exiting...")


if __name__ == "__main__":
    main()  # pragma: no cover
