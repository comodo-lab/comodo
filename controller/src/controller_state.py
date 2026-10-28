import copy
from typing import Any
from datetime import datetime
import time as t

from utils.comodo_config import ComodoConfig

import src.publish_error as pub_err


class cstate:
    """
    Represents the state of the controller, including the status and experiment configuration.
    """

    allowed_status = [
        "idle",
        "validating",
        "starting",
        "awaiting_instruments",
        "ready",
        "running",
        "stopping",
        "error",
    ]

    __slots__ = [
        "_experiment_start_time",
        "_experiment_id",
        "_exp_file",
        "_status",
        "_exp_config",
        "_setpoints",
        "_current_setpoint",
        "_past_setpoints",
        "_instrument_states",
        "_config",
        "_expected_heartbeats",
        "_instruments_ready",
        "_no_contact_tolerance",
        "_adjusting_tolerance",
    ]

    def __init__(self) -> None:
        """
        Initializes a new instance of the cstate class.
        """
        self.experiment_start_time: datetime = None
        self.experiment_id: str = None
        self.exp_file: str = None
        self.status: str = "idle"
        self.exp_config: dict[str, Any] = None
        self.setpoints: list[dict[str, Any]] = []
        self.current_setpoint: dict[str, Any] = None
        self.past_setpoints: list[dict[str, Any]] = []
        self.instrument_states: dict[str, Any] = {}
        self.expected_heartbeats: dict[str, Any] = {}
        self.instruments_ready: bool = False
        self.config: ComodoConfig = None
        self._no_contact_tolerance: float = None
        self._adjusting_tolerance: float = None

    @property
    def config(self) -> ComodoConfig | None:
        return self._config

    @config.setter
    def config(self, value: ComodoConfig | None) -> None:
        """
        Sets the configuration for the controller state.

        Args:
            value (ComodoConfig | None): The configuration to set. Must be an instance of ComodoConfig or None.
        Raises:
            TypeError: If the provided value is not an instance of ComodoConfig or None.
        """
        if not isinstance(value, (ComodoConfig, type(None))):
            raise TypeError(
                f"Config must be an instance of ComodoConfig or None, got {type(value).__name__}"
            )
        self._config = value
        if value is not None:
            self._no_contact_tolerance = (
                value.globals["max_missed_heartbeats"]
                * value.globals["heartbeat_interval"]
            )

    def heartbeat(self) -> dict[str, Any]:
        """
        Generates a dictionary with the attributes that will get added to the heartbeat mqtt messages.
        """
        variable_eval = self.evaluate_variables()
        self.update_bad_instrument_counts(variable_eval)
        return {
            "config": {"experiment_id": self.experiment_id},
            "setpoints": variable_eval["setpoints"],
            "state": {
                "status": self.status,
                "variables": variable_eval["status"],
            },
        }

    def reset(self) -> None:
        """
        Resets the state of the controller to its initial values.
        """
        self.experiment_start_time = None
        self.experiment_id = None
        self.exp_file = None
        self.status = "idle"
        self.exp_config = None
        self.setpoints = []
        self.current_setpoint = None
        self.past_setpoints = []
        self.instrument_states = {}
        self.reset_expected_heartbeats()
        self.instruments_ready = False
        self._adjusting_tolerance = None

    @property
    def experiment_start_time(self) -> datetime:
        return self._experiment_start_time

    @experiment_start_time.setter
    def experiment_start_time(self, value: datetime) -> None:
        """
        Sets the experiment start time, used as a reference when dumping the database.

        Args:
            value: The new experiment start time value. Must be a datetime object or None.

        Raises:
            TypeError: If the provided experiment start time is not a datetime object or None.
        """
        if not isinstance(value, (datetime, type(None))):
            raise TypeError(
                f"Experiment start time must be a datetime or None, cannot accept {type(value)}"
            )
        self._experiment_start_time = value

    @property
    def experiment_id(self) -> str:
        return self._experiment_id

    @experiment_id.setter
    def experiment_id(self, value: str) -> None:
        """
        Sets the experiment UID.

        Args:
            value: The new experiment UID value. Must be a string or None.

        Raises:
            TypeError: If the provided experiment UID is not a string or None.
        """
        if not isinstance(value, (str, type(None))):
            raise TypeError(
                f"Experiment UID must be a string or None, cannot accept {type(value)}"
            )
        self._experiment_id = value

    @property
    def exp_file(self) -> str:
        return self._exp_file

    @exp_file.setter
    def exp_file(self, value: str) -> None:
        """
        Sets the experiment file path.

        Args:
            value: The new experiment file path value. Must be a string or None.

        Raises:
            TypeError: If the provided experiment file path is not a string or None.
        """
        if not isinstance(value, (str, type(None))):
            raise TypeError(
                f"Experiment file path must be a string or None, cannot accept {type(value)}."
            )
        self._exp_file = value

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """
        Sets the status of the controller.

        Args:
            value: The new status value. Must be one of the allowed status values.

        Raises:
            ValueError: If the provided status is not one of the allowed status values.
        """
        if value not in self.allowed_status:
            raise ValueError(
                f"Invalid status: {value}. Status must be one of {self.allowed_status}."
            )
        self._status = value

    @property
    def exp_config(self) -> dict[str, Any]:
        return self._exp_config

    @exp_config.setter
    def exp_config(self, value: dict[str, Any]) -> None:
        """
        Sets the experiment configuration.

        Args:
            value: The new experiment configuration dict.

        Raises:
            TypeError: If the provided experiment configuration is not a dictionary or None.
        """
        if not isinstance(value, (dict, type(None))):
            raise TypeError(
                f"Experiment configuration must be a dictionary or None, cannot accept {type(value)}."
            )
        self._exp_config = value
        if value is not None and self.config is not None:
            self._adjusting_tolerance = (
                self.config.globals["missed_setpoint_tolerance"]
                * value["config"]["resolution"]
                / self.config.globals["heartbeat_interval"]
            )

    @property
    def setpoints(self) -> list[dict[str, Any]]:
        return self._setpoints

    @setpoints.setter
    def setpoints(self, value: list[dict[str, Any]]) -> None:
        """
        Sets the setpoints list.

        Args:
            value: The new setpoints list.

        Raises:
            TypeError: If the provided setpoints list is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(
                f"Setpoints must be a list of dictionaries, cannot accept {type(value)}."
            )
        self._setpoints = value

    @property
    def current_setpoint(self) -> dict[str, Any]:
        return self._current_setpoint

    @current_setpoint.setter
    def current_setpoint(self, value: dict[str, Any]) -> None:
        """
        Sets the current setpoint.

        Args:
            value: The new value for the entire current setpoint.

        Raises:
            TypeError: If the provided current setpoint dictionary is not a dictionary or None.
        """
        if not isinstance(value, (dict, type(None))):
            raise TypeError(
                f"Current setpoint must be a dictionary or None, cannot accept {type(value)}."
            )
        self._current_setpoint = value

    @property
    def past_setpoints(self) -> list[dict[str, Any]]:
        return self._past_setpoints

    @past_setpoints.setter
    def past_setpoints(self, value: list[dict[str, Any]]) -> None:
        """
        Sets the past setpoints list.

        Args:
            value: The new past setpoints list.

        Raises:
            TypeError: If the provided past setpoints list is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(
                f"Past setpoints must be a list of dictionaries, cannot accept {type(value)}."
            )
        self._past_setpoints = value

    @property
    def instrument_states(self) -> dict[str, Any]:
        return self._instrument_states

    @instrument_states.setter
    def instrument_states(self, value: dict[str, Any]) -> None:
        """
        Sets the instrument states dictionary.

        Args:
            value: The new value for the entire instrument states dictionary.

        Raises:
            TypeError: If the provided instrument states dictionary is not a dictionary.
        """
        if not isinstance(value, dict):
            raise TypeError(
                f"Instrument states must be a dictionary, cannot accept {type(value)}."
            )
        self._instrument_states = value

    @property
    def expected_heartbeats(self) -> dict[str, Any]:
        return self._expected_heartbeats

    @expected_heartbeats.setter
    def expected_heartbeats(self, value: dict[str, Any]) -> None:
        """
        Sets the expected heartbeats dictionary.

        Args:
            value: The new value for the entire expected heartbeats dictionary.

        Raises:
            TypeError: If the provided expected heartbeats dictionary is not a dictionary.
        """
        if not isinstance(value, dict):
            raise TypeError(
                f"Expected heartbeats must be a dictionary, cannot accept {type(value)}."
            )
        self._expected_heartbeats = value

    def reset_expected_heartbeats(self) -> None:
        """
        Sets the expected heartbeats dictionary with an empty experiment section.
        """
        expected_heartbeats = {}
        for instrument_name in self.config.instruments:
            exp_hb = self.config.get_expected_heartbeat(instrument_name)
            exp_hb["experiment"] = {}
            expected_heartbeats[instrument_name] = exp_hb
        self.expected_heartbeats = expected_heartbeats

    def set_hb_experiment_config(self, instrument_name: str, experiment_config) -> None:
        """
        Sets the expected heartbeat's experiment configuration for a specific instrument.

        Args:
            instrument_name: The name of the instrument for which to set the expected heartbeat.
            experiment_config: The experiment configuration for the expected heartbeat.
        """
        current_config = self._expected_heartbeats[instrument_name]["experiment"]
        for key, value in experiment_config.items():
            if current_config.get(key, None) is not None:
                print(
                    "WARNING: Replacing existing experiment configuration for "
                    f"instrument {instrument_name} {key}: {current_config[key]} -> {value}."
                )
            self._expected_heartbeats[instrument_name]["experiment"][key] = value

    def get_expected_heartbeat(self, instrument_name: str) -> dict[str, Any]:
        """
        Retrieves the expected heartbeat configuration for a specific instrument.

        Args:
            instrument_name: The name of the instrument for which to retrieve the expected heartbeat.

        Returns:
            The expected heartbeat configuration for the specified instrument or None if the instrument is not found.
        """
        return self._expected_heartbeats.get(instrument_name, None)

    @property
    def instruments_ready(self) -> bool:
        return self._instruments_ready

    @instruments_ready.setter
    def instruments_ready(self, value: bool) -> None:
        """
        Sets the instruments_ready flag.

        Args:
            value: The new value for the instruments_ready flag. Must be a boolean.

        Raises:
            TypeError: If the provided value is not a boolean.
        """
        if not isinstance(value, bool):
            raise TypeError(
                f"Instruments ready flag must be a boolean, cannot accept {type(value)}."
            )
        self._instruments_ready = value

    def evaluate_variables(self) -> dict[str, Any]:
        """
        Evaluates whether instruments are at the expected setpoints and returns a summary.

        Returns:
            A dictionary containing the setpoints used in the evaluation and the instrument evaluation.
        """
        if not self.current_setpoint:
            return {"setpoints": {}, "status": {}}
        t_now = t.time()
        current_setpoints = {
            k: v for k, v in self.current_setpoint.items() if k != "duration"
        }
        ins_states = self.instrument_states
        inst_measurements = {
            f"{inst}/{var}": ins_states[inst]["state"]["measurements"][var]
            for inst in ins_states
            for var in ins_states[inst]["state"]["measurements"]
        }

        variable_evaluation = {}
        for variable, setpoint in current_setpoints.items():
            inst, var = variable.split("/")
            if t_now - ins_states[inst]["last_contact"] > self._no_contact_tolerance:
                variable_evaluation[variable] = "no_heartbeat"
            elif inst_measurements.get(variable, None) is None:
                variable_evaluation[variable] = "no_measurement"
            else:

                if (
                    abs(setpoint - inst_measurements[variable])
                    <= self.exp_config["config"]["instruments"][inst][var]["tolerance"]
                ):
                    variable_evaluation[variable] = "at_setpoint"
                else:
                    variable_evaluation[variable] = "adjusting"
        return {
            "setpoints": current_setpoints,
            "status": variable_evaluation,
        }

    def update_bad_instrument_counts(self, variable_evaluation: dict) -> None:
        """
        Updates the bad instrument count based on the variable evaluation,
        and compares it to the bad instrument tolerance.
        If any instrument exceeds the tolerance, the controller status is set to "error".
        """
        if variable_evaluation.get("status", {}) == {}:
            return
        for inst, iconfig in self.config.instruments.items():
            bad_state = False
            adjusting = False
            for var in iconfig["variables"]:
                status = variable_evaluation["status"].get(f"{inst}/{var}", None)
                if status is None or status == "at_setpoint":
                    continue
                if status in ["no_heartbeat", "no_measurement"]:
                    bad_state = True
                    continue
                if status == "adjusting":
                    adjusting = True
                    continue

            self.instrument_states[inst]["bad_count"] = {
                "bad_state": (
                    0
                    if not bad_state
                    else (
                        self.instrument_states[inst]
                        .get("bad_count", {})
                        .get("bad_state", 0)
                        + 1
                    )
                ),
                "adjusting": (
                    0
                    if not adjusting and not bad_state
                    else (
                        self.instrument_states[inst]
                        .get("bad_count", {})
                        .get("adjusting", 0)
                        + int(adjusting)
                    )
                ),
            }
            if bad_state or adjusting:
                if (
                    self.instrument_states[inst]["bad_count"]["bad_state"]
                    > self.config.globals["bad_state_tolerance"]
                ):
                    pub_err.print_and_publish(
                        topic="error/controller",
                        code="experiment",
                        message=f"ERROR: Instrument {inst} in bad state for too long.",
                    )
                    self.status = "error"
                if (
                    self.instrument_states[inst]["bad_count"]["adjusting"]
                    > self._adjusting_tolerance
                ):
                    pub_err.print_and_publish(
                        topic="error/controller",
                        code="experiment",
                        message=f"ERROR: Instrument {inst} not keeping up with setpoints.",
                    )
                    self.status = "error"
