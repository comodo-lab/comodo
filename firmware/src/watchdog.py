import json
import threading
import time

import utils.mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val


class FirmwareWatchdog:
    """
    Independent client that monitors the controller's heartbeat.
    If no valid heartbeats are received in MAX_MISSED_HEARTBEATS x HEARTBEAT_INTERVAL seconds,
    the watchdog triggers a safe stop.

    This is meant to handle network and controller failures, as the controller can then no longer stop the instrument.

    The watchdog is armed by the first heartbeat from the controller, so the firmware can run without a controller.
    Once a heartbeat is received, the watchdog will safe stop the instrument if it doesn't hear from the controller again.

    When an experiment is running (i.e. the instrument's experiment_id is not None),
    the watchdog only counts a heartbeat as valid if it is for the same experiment.
    This way, if the controller restarts and loses the experiment, or if the experiment's end or stop was missed,
    the instrument will safe stop, instead of continuing to run an experiment that the controller doesn't know about.

    The watchdog also listens for a reset command from the controller (controller/command/reset),
    which returns the instrument to its default setpoints and awaiting_experiment status,
    and disarms the watchdog until the next heartbeat, as if the firmware had just started.
    """

    def __init__(self, istate):
        """
        Creates the watchdog's MQTT client.

        The watchdog only starts checking once 'start' is called.
        It will only trigger a safe stop once armed, which happens when the first controller heartbeat is received.

        Args:
            istate: InstrumentState: The state of the instrument to safe stop, or reset
        """
        self.istate = istate
        config = istate.instrument.config
        self.interval = config["HEARTBEAT_INTERVAL"]
        self.timeout = config["MAX_MISSED_HEARTBEATS"] * config["HEARTBEAT_INTERVAL"]
        # Not armed until the controller is first heard from
        self.last_contact = None
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self.run, daemon=True)
        self.client = mqtt.MQTTClient(
            id=f"{config['INSTRUMENT_NAME']}_watchdog",
            callback=self.on_message,
            topics=["controller/heartbeat", "controller/command/reset"],
            broker_address=config["MQTT_HOST"],
            user=config["MQTT_USER"],
            password=config["MQTT_PASS"],
            connection_timeout=60,
        )

    def start(self):
        """
        Starts checking the controller's heartbeat.
        """
        self._thread.start()

    def stop(self):
        """
        Stops checking the controller's heartbeat.
        """
        self._stopped.set()

    def run(self):
        """
        Checks the controller's heartbeat every HEARTBEAT_INTERVAL seconds
        """
        while not self._stopped.wait(self.interval):
            self.check()

    def check(self):
        """
        Checks if the controller heartbeat is actively being heard,
        or triggers a safe stop if it hasn't (once armed).
        """
        if self.last_contact is None or self.istate.status == "safe_stop":
            return
        silence = time.monotonic() - self.last_contact
        if silence > self.timeout:
            self.istate.safe_stop(
                f"No valid heartbeats from the controller for more than {self.timeout:.1f}s."
            )

    def on_message(self, _client, msg, _obj=None):
        """
        Validates incoming messages and redirects them to the appropriate handler.
        """
        try:
            message = mqtt_val.validate_message(msg.topic, msg.payload)
        except mqtt_val.MQTTValidationException as e:
            print(f"WARNING: Ignoring invalid message on {msg.topic}: {e}")
            return
        if msg.topic == "controller/heartbeat":
            self.on_heartbeat(message)
        elif msg.topic == "controller/command/reset":
            self.on_reset(message)

    def on_heartbeat(self, heartbeat):
        """
        Updates the controller's last contact time, therefore arming the watchdog (even with mismatched experiment IDs).
        If the instrument is currently running an experiment, the experiment id must match.
        """
        if self.last_contact is None:
            self.last_contact = time.monotonic()
            print(f"{self.istate.instrument.config['INSTRUMENT_NAME']} watchdog armed.")
            return
        inst_exp_id = self.istate.instrument.config["experiment"].get("experiment_id")
        hb_exp_id = heartbeat["config"].get("experiment_id")
        if inst_exp_id is None or hb_exp_id == inst_exp_id:
            self.last_contact = time.monotonic()

    def on_reset(self, msg):
        """
        Resets the instrument: goes to its default setpoints, sets status to awaiting an experiment,
        and disarms the watchdog until a controller heartbeat is received.

        If it ends an experiment, it is published as an error, so it doesn't go unnoticed
        (e.g. the controller restarted mid-experiment), unless it was requested from the UI.
        """
        self.last_contact = None
        inst_exp_id = self.istate.instrument.config["experiment"].get("experiment_id")
        source = msg.get("source", "unknown source")
        name = self.istate.instrument.config["INSTRUMENT_NAME"]
        if inst_exp_id is not None:
            message = f"[{name}] Experiment {inst_exp_id} ended by reset from {source}."
            if source == "ui":
                print(f"WARNING: {message}")
            else:
                print(f"ERROR: {message}")
                try:
                    mqtt.MQTTPublisher.get_instance().publish(
                        "error/instrument",
                        json.dumps({"code": "experiment_reset", "message": message}),
                    )
                except mqtt.MQTTMessageError as e:
                    print(f"WARNING: Could not publish the experiment reset: {e}")
        elif self.istate.status == "safe_stop":
            print(f"[{name}] Safe stop cleared by a reset from {source}.")
        self.istate.reset()
