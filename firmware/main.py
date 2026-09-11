# System imports
import asyncio
import json
import os
import traceback

from src import config, state

from utils import mqtt_clients as mqtt

## ----------------- Timer functions ----------------- ##


async def heartbeat_tick(istatus):
    while True:
        istatus.publish_heartbeat()
        await asyncio.sleep(istatus.instrument.config["HEARTBEAT_INTERVAL"])


async def measurement_tick(istatus, variable_name, interval, ready_event):
    first_measurement = True

    while True:
        value = istatus.instrument.measure_or_simulate(variable_name)
        istatus.client.publish(
            f"instruments/{istatus.instrument.config['INSTRUMENT_NAME']}/"
            f"{variable_name}/measurement",
            json.dumps({"value": value}),
        )
        if first_measurement:
            ready_event.set()
            first_measurement = False
        await asyncio.sleep(interval)


# ----------------- Sensor Initialization ----------------- ##


# Publish the default setpoint for each variable to the MQTT broker.
# This is done at startup and whenever the setpoints are reset to default.
def publish_default_setpoints(istatus):
    for variable, setpoint in (
        istatus.instrument.config.get("DEFAULT_SETPOINTS") or {}
    ).items():
        istatus.instrument.setpoints[variable] = setpoint
        mqtt.MQTTPublisher.get_instance().publish(
            f"instruments/{istatus.instrument.config['INSTRUMENT_NAME']}/{variable}/setpoint",
            json.dumps({"value": setpoint}),
        )


async def start_sensors_measurements(istatus, instrument_ready_event, timeout=None):
    sensors = istatus.instrument.config["MEASUREMENT_INTERVALS"]
    if not sensors:
        raise RuntimeError(
            f"No sensors configured for {istatus.instrument.config['INSTRUMENT_NAME']}"
        )
    ready_events = {
        sensor_name: asyncio.Event() for sensor_name in list(sensors.keys())
    }
    async with asyncio.TaskGroup() as tg:
        # Create a measurement tick for each sensor in the instrument's configuration.
        for sensor_name, measurement_interval in sensors.items():
            tg.create_task(
                measurement_tick(
                    istatus,
                    sensor_name,
                    measurement_interval,
                    ready_events[sensor_name],
                )
            )
        # Wait for all sensors to produce their first measurement, or timeout
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*(event.wait() for event in ready_events.values()))
        except TimeoutError as e:
            raise RuntimeError("Sensors failed to initialise in time") from e
        # Signal that the instrument is ready after all sensors have produced their first measurement
        instrument_ready_event.set()

        # Keep the measurement ticks TaskGroup alive indefinitely
        await asyncio.Future()


# ----------------- Main function ----------------- ##


async def main():
    istatus = state.InstrumentStatus(config.load_config())

    # Synchronously launch the measurement ticks for each variable
    instrument_ready_event = asyncio.Event()
    measurement_task = asyncio.create_task(
        start_sensors_measurements(istatus, instrument_ready_event, timeout=10)
    )
    # Wait until every sensor has produced its first measurement
    ready_task = asyncio.create_task(instrument_ready_event.wait())
    done, _ = await asyncio.wait(
        {measurement_task, ready_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    # Propagate exceptions if any of the tasks failed
    if measurement_task in done:
        measurement_task.result()

    # Start instrument in ready state
    istatus.state = "ready"

    # Publish default setpoints for each variable that has one
    # (which triggers the instrument to go to that setpoint)
    publish_default_setpoints(istatus)

    # Print the instrument creation success message
    print(
        f"Instrument {istatus.instrument.config['INSTRUMENT_NAME']} created successfully "
        f"using firmware {istatus.instrument.config['FIRMWARE']}"
    )

    # Start the heartbeat ticks
    heartbeat_task = asyncio.create_task(heartbeat_tick(istatus))

    # Keep running forever
    await asyncio.gather(measurement_task, heartbeat_task)

    return 0


if __name__ == "__main__":
    # Initialise publisher singleton
    _ = mqtt.MQTTPublisher.get_instance(
        broker_address=os.getenv("MQTT_HOST", "rabbitmq"),
        user=os.getenv("MQTT_USER", "comodo"),
        password=os.getenv("MQTT_PASS", "comodo"),
        id=f"publisher_{os.getenv("INSTRUMENT_NAME", "no_name")}",
    )
    try:
        asyncio.run(main())
    except Exception as e:
        traceback.print_exc()
        mqtt.MQTTPublisher.get_instance().publish(
            "error/instrument",
            json.dumps(
                {
                    "code": "exception",
                    "message": f"[{os.getenv('INSTRUMENT_NAME', 'no_name')}] {e}",
                }
            ),
        )
