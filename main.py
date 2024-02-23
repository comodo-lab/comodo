# Micropython imports
from lib.umqtt import MQTTClient

# System imports
import time as t
import sys

# Local imports
import config as cfg
import network as net

# Determine the board and set the watchdog timer
ryboard = sys.platform
if board == "rp2":
    #from machine import WDT
    #wdt = WDT(timeout=2000) # ms



    Returns:
        None
    """
    

def main():
    """ The main function

    Returns:
        int: The exit code
    """
    
    ## Load the configuration file
    config = cfg.load_config()

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        net.connect_wifi(config["WIFI_SSID"], config["WIFI_PASS"])

    ## Connect to the mqtt broker
    client = net.connect_mqtt(config["MQTT_IP"],
                              port=1883,
                              user="sensor",
                              password="foobar!!")


if __name__ == "__main__":
    sys.exit(main())
