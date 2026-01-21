# System imports
import time as t
import sys
import traceback
import json
import asyncio

# Local imports
import config as cfg
import connect as con
import state

# Sensor imports (trigger sensor registration)
from sensors.carbolite_gero_thermocouple import TempLeft, TempMain, TempRight
from sensors.pfeiffer_mpt_200_pressure import PressureDownstream, PressureUpstream
from sensors.el_flow_select_massflow import (
    MassFlow,
    MassFlowTemp,
    MassFlowPressureUpstream,
    MassFlowPressureDownstream,
    MassFlowFluidTemp,
)
from sensors.pfeiffer_prismapro import MassSpec

# Initialize the state
state = state.SensorState()


## ----------------- Timer helper functions ----------------- ##


def send_heartbeat():
    """
    Send the heartbeat

    Returns:
        None
    """
    if state.client is not None and "ready" in state.config:
        heartbeat_structure = state.get_status()
        state.client.publish(
            f"heartbeat/sensor/{state.config['SENSOR_ID']}", heartbeat_structure
        )


def send_measurement():
    """
    Send the measurement

    Returns:
        None
    """

    # Return if the client or sensor is not ready
    if (state.client is None) or (state.sensor is None):
        return

    # Retrieve the measurement 
    if state.config['SIMULATE']:
        measurement = state.sensor.simulate_get_measurement(state)
    else:
        measurement = state.sensor.get_measurement(state)

    # Publish the measurement
    measurement_structure = {"value": measurement}
    msg = json.dumps(measurement_structure)
    state.client.publish(f"measurement/{state.config['SENSOR_ID']}", msg)

    # If ready and setpoint is recieved that is beyond tolerance way, move to it
    if state.status["status"] != "ready":
        return

    position = measurement - state.status["setpoint"]
    if abs(position) > state.status["config"]["tolerance"]:
        # Change state
        state.client.set_callback(state.adjusting_cb)
        state.status["status"] = "adjusting"

        # Move to setpoint
        if state.config['SIMULATE']:
            state.sensor.simulate_go_to_setpoint(state.status["setpoint"])
        else:
            state.sensor.go_to_setpoint(state.status["setpoint"])            

        
## ----------------- Timer functions ----------------- ##


async def heartbeat_tick(timer):
    while True:
        send_heartbeat()
        await asyncio.sleep(int(state.config["HEARTBEAT_INTERVAL"]) / 1000)

async def measurement_tick(timer):
    while True:
        send_measurement()
        await asyncio.sleep(int(state.config["MEASUREMENT_INTERVAL"]) / 1000)

# ----------------- Main function ----------------- ##


# The main function
async def main():
    """
    The main function

    Returns:
        int: The exit code
    """

    ## Load the configuration file
    state.config = cfg.load_config()
    state.status["name"] = state.config["SENSOR_ID"]

    ## Determine the board and connect to the wifi if it is a raspberry pi
    if board == "rp2":
        con.connect_wifi(state.config["WIFI_SSID"], state.config["WIFI_PASS"])
        watchdog.feed()

    ## Connect to the mqtt broker
    state.client = con.connect_mqtt(
        state.status["name"],
        state.config["MQTT_HOST"],
        port=1883,
        user=state.config["MQTT_USER"],
        password=state.config["MQTT_PASS"],
    )

    ## Subscribe to the controller's instructions
    state.client.set_callback(state.awaiting_config_cb)
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setup")
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setpoint_reached")
    state.client.subscribe(f"sensor/{state.config['SENSOR_ID']}/setpoint")
    state.client.subscribe(f"controller/end")
    state.client.subscribe(f"controller/stop")

    # Initialise the sensor
    if not state.config['SIMULATE']:
        state.sensor.initialise()
    else:
        print(f" ### Simulating {state.config['SENSOR_ID']} ### ")
    
    ## Set the ready flag
    state.config["ready"] = True
    print(f"Sensor {state.config['SENSOR_ID']} is ready")

    ## Setup heartbeat timer if on a pico or async timer if on linux
    asyncio.create_task(heartbeat_tick(None))
    asyncio.create_task(measurement_tick(None))

    # Keep running forever
    await asyncio.Event().wait()

    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        traceback.print_exc()
        try:
            state.client.publish(
                f"error/sensor/{state.config['SENSOR_ID']}", str(e)
            )
        except:
            print(f"Error: {e}")
