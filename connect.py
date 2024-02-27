from lib.umqtt import MQTTClient
import sys
board = sys.platform
if board == "rp2":
    import network
    
def connect_wifi(ssid, password):
    """ Connect to the wifi network

    Returns:
        None
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            pass


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
