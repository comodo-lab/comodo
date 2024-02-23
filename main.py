# Micropython imports

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

    ## Set up subscriptions
    #client.set_callback(sub_cb)
    #client.subscribe(f"sensor/{config['SENSOR_ID']}/#")

    return 0

if __name__ == "__main__":
    sys.exit(main())
