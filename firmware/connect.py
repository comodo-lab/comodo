from lib.umqtt import MQTTClient
import sys
import random

board = sys.platform
if board == "rp2":
    import network
    from machine import Timer

    
def connect_wifi(ssid, password):
    """ Connect to the wifi network

    Returns:
        None

    Raises:
    
    """
    wlan = network.WLAN(network.STA_IF)
    if wlan.isconnected():
        wlan.active(False)
        wlan.disconnect()

    wlan.active(True)        
    wlan.connect(ssid, password)
    while not wlan.isconnected():
        pass


def timeout_mqtt(timer):
    print("Timeout")
    raise Exception("Timeout connecting to the mqtt broker")

    
def connect_mqtt(client_name, ip_address, port=1883, user=None, password=None):
    """ Connect to the mqtt broker
    Args:
        client_name: str: The name of the client
        ip_address: str: The ip address of the mqtt broker
        port: int: The port of the mqtt broker
        user: str: The user of the mqtt broker
        password: str: The password of the mqtt broker
    
    Returns:
        MQTTClient: The mqtt client object
    """
    c = MQTTClient(f'{client_name}-{random.randint(0, 10000)}',
                   ip_address,
                   port=port,
                   user=user,
                   password=password
                   )

    if board == "rp2":
        timeout_timer = Timer(period=5000,
                              mode=Timer.ONE_SHOT,
                              callback=timeout_mqt)
    c.connect()
    if board == "rp2":
        timeout_timer.deinit()
    print(f'Connected to the mqtt broker at {ip_address}:{port}')

    return c
