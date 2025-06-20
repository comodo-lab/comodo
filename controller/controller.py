import sys
import os

sys.path.append(os.path.abspath("src"))

import time as t
import json
import textwrap

from validation import validate_file_print_errors
from controller_state import *
from mqtt_clients import *
from on_watchdog_message import *
from on_watchdog_timer_message import *
from on_ui_message import *
from on_controller_message import *
from on_timer_message import *
from on_heartbeat_message import *


def main():
    print(f"Starting...")
    # Load configuration
    try:
        config = validate_file_print_errors(
            "config/config.json",
            "schemas/schema_config.json",
        )
        wdog = config["watchdog"]
        assert wdog["interval"] > 0
        assert wdog["timeout"] > 2 * wdog["interval"]
        wdog["timer"] = wdog["timeout"]
        wdog["healthy"] = False
    except KeyError as e:
        print(
            f"Error decoding config file, missing: \n{textwrap.indent(str(e), '   ')}"
        )
        exit(1)

    # Initialize controller state
    state = cstate()

    print(f"  Creating clients...")
    broker_address = config["mqtt"]["broker_address"]
    user = config["mqtt"]["user"]
    password = config["mqtt"]["password"]
    connection_timeout = config["mqtt"]["connection_timeout"]

    # Initialise publisher singleton
    publisher = MQTTPublisher(broker_address=broker_address,
                              user=user,
                              password=password,
                              connection_timeout=connection_timeout,
                              )
    
    # Load MQTT clients
    watchdog = MQTTClient(
        id="watchdog",
        callback=on_watchdog_message,
        topics=["watchdog/#", "heartbeat/controller", "ERROR/exception"],
        obj=wdog,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    wd_timer = MQTTClient(
        id="wd_timer",
        callback=on_wd_timer_message,
        topics="wd_timer/#",
        obj=wdog,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    ui = MQTTClient(
        id="ui",
        callback=on_ui_message,
        topics="ui/#",
        obj=state,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    controller = MQTTClient(
        id="controller",
        callback=c_idle,
        topics="controller/#",
        obj=state,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    timer = MQTTClient(
        id="timer",
        callback=on_timer_message,
        topics="timer/#",
        obj=state,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    heartbeat = MQTTClient(
        id="heartbeat",
        callback=on_heartbeat_message,
        topics="heartbeat/sensor/#",
        obj=state,
        broker_address=broker_address,
        user=user,
        password=password,
        connection_timeout=connection_timeout,
    )
    # measurement = MQTTClient("measurement", on_client_message, topics="measurement/#")

    publisher.client.publish("wd_timer/start", json.dumps(wdog))
    t.sleep(1)
    if wdog["healthy"]:
        print(f"Controller started successfully.")
    while wdog["healthy"]:
        controller.publish("heartbeat/controller", f"{state}")
        t.sleep(wdog["interval"])

    print(f"Exiting...")


if __name__ == "__main__":
    main()
