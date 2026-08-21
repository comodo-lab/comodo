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
    if state.client is not None and "ready" in state.status["state"]:
        heartbeat_structure = state.get_status()
        state.client.publish(
            f"instruments/{state.config['INSTRUMENT_NAME']}/heartbeat",
            heartbeat_structure,
        )


## ----------------- Timer functions ----------------- ##


async def heartbeat_tick():
    while True:
        send_heartbeat()
        await asyncio.sleep(int(state.config["HEARTBEAT_INTERVAL"]) / 1000)


async def measurement_tick(variable_name, interval, oneshot=False):
    while True:
        value = state.instrument.get_measurement(state, variable_name)
        state.client.publish(
            f"instruments/{state.config['INSTRUMENT_NAME']}/{variable_name}/measurement",
            json.dumps({"value": value}),
        )
        await asyncio.sleep(interval / 1000)

        if oneshot:
            break


# ----------------- Launcher ----------------- ##


# Publish the default setpoint for each variable to the MQTT broker.
# This is done at startup and whenever the setpoints are reset to default.
def publish_default_setpoints():
    for variable, setpoint in (state.config.get("DEFAULT_SETPOINTS") or {}).items():
        state.status["setpoints"][variable] = setpoint
        mqtt.MQTTPublisher.get_instance().publish(
            f"instruments/{state.config['INSTRUMENT_NAME']}/{variable}/setpoint",
            json.dumps({"value": setpoint}),
        )


async def launcher(oneshot=False, timeout=None):
    try:
        async with asyncio.timeout(timeout):
            async with asyncio.TaskGroup() as tg:
                for variable in state.config["SENSORS"].values():
                    tg.create_task(
                        measurement_tick(
                            variable["name"],
                            variable["interval"],
                            oneshot=oneshot,
                        )
                    )
    except TimeoutError as e:
        raise RuntimeError("Sensors failed to initialise in time") from e


# ----------------- Main function ----------------- ##


async def main():
    """
    The main function

    Returns:
        int: The exit code
    """

    ## Load the configuration file
    state.config = cfg.load_config()

    # Initialise publisher singleton
    _ = mqtt.MQTTPublisher.get_instance(
        broker_address=state.config["MQTT_HOST"],
        user=state.config["MQTT_USER"],
        password=state.config["MQTT_PASS"],
        id=f"publisher_{state.config['INSTRUMENT_NAME']}",
    )

    ## Create client
    topics = [
        f"instruments/{state.config['INSTRUMENT_NAME']}/+/setpoint",
        f"controller/event/end",
        f"controller/command/stop",
    ]
    state.client = mqtt.MQTTClient(
        id=state.config["INSTRUMENT_NAME"],
        callback=state.idle_cb,
        topics=topics,
        broker_address=state.config["MQTT_HOST"],
        user=state.config["MQTT_USER"],
        password=state.config["MQTT_PASS"],
        connection_timeout=60,
    )

    # Create and initialise the instrument
    state.instrument = BaseInstrument.create_instrument(state.config["FIRMWARE"])
    state.instrument.initialise(state)

    cfg.populate_heartbeat(state)

    # Attempt startup
    await launcher(oneshot=True, timeout=10)

    # If successful, set ready, publish (and go to) the default setpoints and print the instrument creation message
    state.status["state"] = "ready"
    state.client.callback = state.ready_cb

    # Populate heartbeat config
    state.status["config"] = state.config.get("HEARTBEAT", {}).copy()

    # Publish default setpoints for each variable that has one
    publish_default_setpoints()

    print(
        f"Instrument {state.config['INSTRUMENT_NAME']} created successfully "
        f"using firmware {state.config['FIRMWARE']}"
    )

    # Keep running forever
    asyncio.create_task(heartbeat_tick())
    await launcher()

    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        traceback.print_exc()
        try:
            state.client.publish(
                "error/instrument",
                json.dumps(
                    {
                        "code": "exception",
                        "message": f"[{state.config['INSTRUMENT_NAME']}] {e}",
                    }
                ),
            )
        except:
            print(f"Error: {e}")
