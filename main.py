# Micropython imports
import ujson 

# System imports
import time as t
import sys

# Local imports
import config as cfg
import connect as con

import sensor_state

state = sensor_state.SensorState()

# Determine the board and set the watchdog timer
board = sys.platform
if board == "rp2":
    from machine import Timer
#     from machine import WDT
#    wdt = WDT(timeout=2000) # ms

# Define heartbeat publishing
def heartbeat_tick(timer):
    """ The heartbeat function

    Args:
        timer: Timer: The timer object

    Returns:
        None
    """

    global client

    if state.client is not None and "ready" in state.config:
        heartbeat_structure = state.get_status()
        state.client.publish(f"heartbeat/sensor/{state.config['SENSOR_ID']}", heartbeat_structure)
        print(heartbeat_structure)

    
def main():
    """ The main function

    Returns:
        int: The exit code
    """
    global config
    
    ## Load the configuration file
    state.config = cfg.load_config()
    state.status["name"] = state.config['SENSOR_ID']

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        con.connect_wifi(state.config["WIFI_SSID"], state.config["WIFI_PASS"])

    ## Connect to the mqtt broker
    state.client = con.connect_mqtt(state.config["MQTT_IP"],
                                    port=1883,
                                    user="sensor",
                                    password="foobar!!")
    
    ## Setup heartbeat timer
    if board == "rp2":
        print(state.config["HEARTBEAT_INTERVAL"])
        timer = Timer(period=state.config["HEARTBEAT_INTERVAL"],
                      mode=Timer.PERIODIC,
                      callback=heartbeat_tick)

    ## Subscribe to the controller's instructions
    state.client.set_callback(state.idle_cb)
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setup")
    state.client.subscribe(f"sensor/setpoint")

    ## Set the ready flag
    state.config['ready'] = True

    ## Main loop
    while True:
        state.client.wait_msg()
        t.sleep(1)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
