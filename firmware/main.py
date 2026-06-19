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
            f"instruments/{state.config['INSTRUMENT_NAME']}/heartbeat", heartbeat_structure
        )


## ----------------- Timer functions ----------------- ##


async def heartbeat_tick():
    while True:
        send_heartbeat()
        await asyncio.sleep(int(state.config["HEARTBEAT_INTERVAL"]) / 1000)


async def measurement_tick(variable):
    while True:
        interval = int(state.config.get(f"INTERVAL_{variable.upper()}", 1000))
        value = state.instrument.get_measurement(state, variable)
        state.client.publish(
            f"instruments/{state.config['INSTRUMENT_NAME']}/{variable}/measurement",
            json.dumps({"value": value}),
        )
        await asyncio.sleep(interval / 1000)


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

    # Self-test: read each sensor variable once
    all_ok = True
    for var, var_config in state.instrument.variables.items():
        if "sensor_param" not in var_config:
            continue
        try:
            val = state.instrument.get_measurement(state, var)
            if val is None:
                all_ok = False
        except Exception:
            all_ok = False

    if all_ok and state.instrument.variables:
        state.status["state"] = "ready"
        state.client.callback = state.ready_cb
        print(f"Instrument {state.config['INSTRUMENT_NAME']} ready")
    else:
        print(f"Instrument {state.config['INSTRUMENT_NAME']} self-test failed, staying idle")

    simulate = state.config.get("SIMULATE", False)
    if isinstance(simulate, str):
        simulate = simulate.lower() in ("true", "1", "yes")
    state.status["config"] = {
        "firmware": state.config.get("FIRMWARE"),
        "device_address": state.config.get("DEVICE_ADDRESS"),
        "simulate": simulate,
        "intervals": {
            var: int(state.config.get(f"INTERVAL_{var.upper()}", 1000))
            for var in state.instrument.variables
        },
        "variables": state.instrument.variables,
    }
    state.config["ready"] = True

    print(
        f"Instrument {state.config['INSTRUMENT_NAME']} created successfully "
        f"using firmware {state.config['FIRMWARE']}"
    )

    ## Setup heartbeat and per-variable measurement tasks
    asyncio.create_task(heartbeat_tick())
    for var, var_config in state.instrument.variables.items():
        if "sensor_param" in var_config:
            asyncio.create_task(measurement_tick(var))

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
                json.dumps({"code": "exception", "message": f"[{state.config['INSTRUMENT_NAME']}] {e}"}),
            )
        except:
            print(f"Error: {e}")
