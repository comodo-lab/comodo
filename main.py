# Micropython imports
import ujson 

# System imports
import time as t
import sys

# Local imports
import config as cfg
import connect as con

# Determine the board and set the watchdog timer
board = sys.platform
if board == "rp2":
    from machine import Timer
#     from machine import WDT
#    wdt = WDT(timeout=2000) # ms

# Set the heartbeat_state
heartbeat_state = {
    "name": "---",
    "status": "awaiting_config",
    "setpoint": 0,
    "temperture": 0,
    "config": {
        "p": 0,
        "i": 0,
        "d": 0,
        "tolerance": 0
    },
}

# Define heartbeat publishing
def heartbeat_tick(timer):
    """ The heartbeat function

    Args:
        timer: Timer: The timer object

    Returns:
        None
    """

    global client

    if "client" in config and config['ready'] is True:
        print("Tick!")
        heartbeat_structure = ujson.dumps(heartbeat_state)
        config['client'].publish(f"heartbeat/sensor/{config['SENSOR_ID']}", heartbeat_structure)

def sub_cb(topic, msg):
    """ The callback function for the mqtt client

    Args:
        topic: str: The topic of the message
        msg: str: The message

    Returns:
        None
    """
    print(topic, msg)
    

def main():
    """ The main function

    Returns:
        int: The exit code
    """
    global config
    
    ## Load the configuration file
    config = cfg.load_config()
    heartbeat_state["name"] = config['SENSOR_ID']

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        con.connect_wifi(config["WIFI_SSID"], config["WIFI_PASS"])

    ## Connect to the mqtt broker
    config['client'] = con.connect_mqtt(config["MQTT_IP"],
                                        port=1883,
                                        user="sensor",
                                        password="foobar!!")
    
    ## Setup heartbeat timer
    if board == "rp2":
        print(config["HEARTBEAT_INTERVAL"])
        timer = Timer(period=config["HEARTBEAT_INTERVAL"],
                      mode=Timer.PERIODIC,
                      callback=heartbeat_tick)

    config['ready'] = True
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
