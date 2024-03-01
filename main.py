# Micropython imports
import ujson
import asyncio

# System imports
import time as t
import sys

# Local imports
import config as cfg
import connect as con
import state

# Initialize the state
state = state.SensorState()

# Determine the board and set the watchdog timer
board = sys.platform
if board == "rp2":
    from machine import Timer
#     from machine import WDT
#    wdt = WDT(timeout=20000) # ms

## ----------------- Timer helper functions ----------------- ##

def send_heartbeat():
    """ Send the heartbeat

    Returns:
        None
    """
    if state.client is not None and "ready" in state.config:
        heartbeat_structure = state.get_status()
        print(heartbeat_structure)
        state.client.publish(f"heartbeat/sensor/{state.config['SENSOR_ID']}", heartbeat_structure)

def send_measurement():
    """ Send the measurement

    Returns:
        None
    """
    if (state.client is not None) and \
       (state.status['setpoint'] is not None) and \
       (state.sensor is not None) :
        measurement = state.sensor.get_measurement(state)
        measurement_structure = {"value": measurement}
        msg = ujson.dumps(measurement_structure)
        state.client.publish(f"measurement/{state.config['SENSOR_ID']}", msg)

## ----------------- Timer functions ----------------- ##

if board == "linux":
    async def heartbeat_tick(timer):
        while True:
            send_heartbeat()
            await asyncio.sleep_ms(state.config["HEARTBEAT_INTERVAL"])
    async def measurement_tick(timer):
        while True:
            send_measurement()
            await asyncio.sleep_ms(state.config["MEASUREMENT_INTERVAL"])
else:
    def heartbeat_tick(timer):
        send_heartbeat()

    def measurement_tick(timer):
        send_measurement()
        
# ----------------- Main function ----------------- ##

# The main function    
async def main():
    """ The main function

    Returns:
        int: The exit code
    """
    
    ## Load the configuration file
    state.config = cfg.load_config()
    state.status["name"] = state.config['SENSOR_ID']

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        con.connect_wifi(state.config["WIFI_SSID"], state.config["WIFI_PASS"])

    ## Connect to the mqtt broker
    state.client = con.connect_mqtt(state.status["name"],
                                    state.config["MQTT_IP"],
                                    port=1883,
                                    user="sensor",
                                    password="foobar!!")

    ## Subscribe to the controller's instructions
    state.client.set_callback(state.awaiting_config_cb)
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setup")
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setpoint_reached")
    state.client.subscribe(f"sensor/setpoint")
    state.client.subscribe(f"controller/end")
    state.client.subscribe(f"controller/stop")

    ## Set the ready flag
    state.config['ready'] = True

    ## Setup heartbeat timer if on a pico or async timer if on linux
    if board == "rp2":
        heartbeat_timer = Timer(period=state.config["HEARTBEAT_INTERVAL"],
                                mode=Timer.PERIODIC,
                                callback=heartbeat_tick)
        measurement_timer = Timer(period=state.config["MEASUREMENT_INTERVAL"],
                                mode=Timer.PERIODIC,
                                callback=measurement_tick)
    elif board == "linux":
        asyncio.create_task(heartbeat_tick(None))
        asyncio.create_task(measurement_tick(None))

    ## Main loop
    while True:
        if board == "rp2":
            # blocking wait for message (since the timer is in hardware)
            state.client.wait_msg()
        elif board == "linux":
            # non-blocking check for message (since the timer is in software)
            state.client.check_msg()
            await asyncio.sleep(0.1)
    
    return 0

if __name__ == "__main__":
    asyncio.run(main())
