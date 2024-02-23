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
#if board == "rp2":
    #from machine import WDT
    #wdt = WDT(timeout=2000) # ms

# Set the state
state = {
    "name": config['SENSOR_ID'],
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
    
    ## Load the configuration file
    config = cfg.load_config()

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        con.connect_wifi(config["WIFI_SSID"], config["WIFI_PASS"])

    ## Connect to the mqtt broker
    client = con.connect_mqtt(config["MQTT_IP"],
                              port=1883,
                              user="sensor",
                              password="foobar!!")


    
    ## Enter the main loop
    while True:
        ## Reset the watchdog timer
        #wdt.feed()

        ## Publish the heartbeat
        heartbeat_structure = ujson.dumps(state)
        client.publish(f"heartbeat/sensor/{config['SENSOR_ID']}", heartbeat_structure)
        t.sleep(1)

    return 0

if __name__ == "__main__":
    sys.exit(main())
