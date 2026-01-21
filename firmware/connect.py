import sys
import random



def connect_wifi(ssid, password):
    """Connect to the wifi network

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


def connect_mqtt(state=None):
    """Connect to the mqtt broker
    Args:
        client_name: str: The name of the client
        ip_address: str: The ip address of the mqtt broker
        port: int: The port of the mqtt broker
        user: str: The user of the mqtt broker
        password: str: The password of the mqtt broker

    Returns:
        MQTTClient: The mqtt client object
    """
    
    ## Subscribe to the controller's instructions
    topics = [
        f"sensor/{state.config['SENSOR_ID']}/setup",
        f"sensor/{state.config['SENSOR_ID']}/setpoint_reached",
        f"sensor/{state.config['SENSOR_ID']}/setpoint",
        f"controller/end",
        f"controller/stop"
    ]

    ## Create client
    c = mqtt.MQTTClient(
            id=state.status["name"],
            callback=state.awaiting_config_cb,
            topics=topics,
            broker_address=state.config["MQTT_HOST"],
            user=state.config["MQTT_USER"],
            password=state.config["MQTT_PASS"]
    )

    if board == "rp2":
        timeout_timer = Timer(period=5000, mode=Timer.ONE_SHOT, callback=timeout_mqtt)
    c.connect()
    if board == "rp2":
        timeout_timer.deinit()
    print(f"Connected to the mqtt broker at {ip_address}:{port}")

    return c
