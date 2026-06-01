# System imports
import traceback
import json
import asyncio

# Shared utils imports
from utils import mqtt_clients as mqtt

# Local imports
import src.config as cfg
import src.state as state

# Instrument imports (trigger instrument registration)
from src.instrument import BaseInstrument

# Initialize the state
state = state.InstrumentState()

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
            f"instruments/{state.config['INSTRUMENT_ID']}/heartbeat", heartbeat_structure
        )


## ----------------- Publishing helper functions ----------------- ##


def publish_measurement(measurements):
    if state.client is None:
        return

    if type(measurements) is int or type(measurements) is float:
        measurements = {"value": measurements}

    for key, measurement in measurements.items():
        msg = json.dumps({"value": measurement})
        state.client.publish(f"instruments/{state.config['INSTRUMENT_ID']}/{key}/measurement", msg)


def send_measurement():
    """
    Send the measurement

    Returns:
        None
    """

    # Return if the client or instrument is not ready
    if (state.client is None) or (state.instrument is None):
        return

    # Retrieve the measurement
    if state.config["SIMULATE"]:
        measurements = state.instrument.simulate_get_measurement(state)
    else:
        measurements = state.instrument.get_measurement(state)

    # Publish the measurement (break lists into individual messages)
    publish_measurement(measurements)


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

    ## Create client
    topics = [
        f"instruments/{state.config['INSTRUMENT_ID']}/setup",
        f"instruments/{state.config['INSTRUMENT_ID']}/+/setpoint",
        f"controller/event/end",
        f"controller/command/stop",
    ]
    state.client = mqtt.MQTTClient(
        id=state.config["INSTRUMENT_ID"],
        callback=state.idle_cb,
        topics=topics,
        broker_address=state.config["MQTT_HOST"],
        user=state.config["MQTT_USER"],
        password=state.config["MQTT_PASS"],
        connection_timeout=60,
    )

    # Create the instrument
    state.instrument = BaseInstrument.create_instrument(state.config["FIRMWARE"])

    # Initialise the instrument
    if not state.config["SIMULATE"]:
        state.instrument.initialise()
    else:
        print(f" ### Simulating {state.config['INSTRUMENT_ID']} ### ")

    ## Set the ready flag
    state.config["ready"] = True
    print(
        f"Instrument {state.config['INSTRUMENT_ID']} created successfully "
        f"using firmware {state.config['FIRMWARE']}"
    )
    print(f"Instrument {state.config['INSTRUMENT_ID']} awaiting configuration.")

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
                "error/instrument",
                json.dumps({"code": "exception", "message": f"[{state.config['INSTRUMENT_ID']}] {e}"}),
            )
        except:
            print(f"Error: {e}")
