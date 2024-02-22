from lib.umqtt import MQTTClient
import ujson as json
import time as t
import sys

def load_config():
    """ Load the configuration file from env.json

    Returns:
        dict: The configuration file
    """
    with open("env.json", "r") as f:
        config = json.loads(f.read())
    print(config)
    return config


def connect_wifi(ssid, password):
    """ Connect to the wifi network

    Returns:
        None
    """
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass
    print('network config:', wlan.ifconfig())
    

def connect_mqtt(ip_address, port=1883, user=None, password=None):
    """ Connect to the mqtt broker

    Args:
        ip_address: str: The ip address of the mqtt broker
        port: int: The port of the mqtt broker
        user: str: The user of the mqtt broker
        password: str: The password of the mqtt broker
    
    Returns:
        MQTTClient: The mqtt client object

    Raises:
        EHOSTUNREACH: The mqtt broker is not reachable
    """
    
    c = MQTTClient("umqtt_client",
                   ip_address,
                   port=port,
                   user=user,
                   password=password
                   )
    c.connect()
    return c

def main():
    ## Load the configuration file
    config = load_config()

    ## Determine the board and connect to the wifi if it is a raspberry pi
    board = sys.platform
    if board == "rp2":
        connect_wifi(config["WIFI_SSID"], config["WIFI_PASS"])

    ## Connect to the mqtt broker
    print("Connecting to mqtt broker")
    client = connect_mqtt(config["MQTT_IP"],
                          port=1883,
                          user="sensor",
                          password="foobar!!")
    print("Connected to mqtt broker")

    oli you need to add the environment variables to the github action

if __name__ == "__main__":
    sys.exit(main())






# count = 0
# while True:
#     temp = count
#     count += 1
#     c.publish(b"/sensor/rpi-tc/temperature",str(temp))
#     t.sleep(1)


    
