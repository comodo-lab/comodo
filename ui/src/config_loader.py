import copy
import uuid

from utils.comodo_config import ComodoConfig
from utils.pid import PID

PID_DEFAULTS = PID().get_config()
PID_NAME_MAP = {
    "k_p": "Proportional",
    "k_i": "Integral",
    "k_d": "Derivative",
    "k_aw": "Anti-Windup",
    "k_df": "Derivative Filter",
    "max_rate": "Max Rate of Change",
}


class UiConfig:
    """UI-specific views over the shared Comodo configuration."""

    def __init__(self, config_path=None, path=None):
        self.config = ComodoConfig(path=config_path or path or "/app/comodo.yaml")
        self.config.load()

    @property
    def params(self):
        names = []
        spc_actuators = {spc["actuator"] for spc in self.config.spcs.values()}
        for actuator_name, actuator in self.config.actuators.items():
            if actuator_name not in spc_actuators:
                names.append(actuator["driving_sensor"])
        names.extend(spc["external_sensor"] for spc in self.config.spcs.values())
        return names

    @property
    def param_dicts(self):
        return [
            {
                "name": name,
                "min": self.config.sensors[name]["min"],
                "max": self.config.sensors[name]["max"],
                "step": 1,
                "default_setpoint": self.config.sensors[name].get(
                    "default_setpoint", 0
                ),
            }
            for name in self.params
        ]

    @property
    def ini_data_dict(self):
        default_row = self.config.get_default_experiment()[0]
        return [{**copy.deepcopy(default_row), "id": str(uuid.uuid4())}]

    @property
    def ini_instrument_dict(self):
        """
        Default instrument live config rows ({name, key, value}), where name is an
        instrument or one of its variables (instrument/variable).
        """
        result = []
        for name, sensor in self.config.sensors.items():
            result.append(
                {
                    "name": name,
                    "key": "tolerance",
                    "value": sensor.get("tolerance", 1.0),
                }
            )
        for name in self.config.actuators:
            if name not in self.config.sensors:
                result.append({"name": name, "key": "tolerance", "value": 1.0})
        return result

    @property
    def ini_spc_dict(self):
        """
        Default setpoint controller rows ({name, k_p, ...}) with the PID parameters
        from comodo.yaml, or the PID defaults if not set
        """
        return [
            {
                "name": spc_id,
                **{
                    key: spc.get(key.upper(), PID_DEFAULTS[key])
                    for key in PID_NAME_MAP
                },
            }
            for spc_id, spc in self.config.spcs.items()
        ]

    @property
    def ini_experiment_config(self):
        return [
            {
                "name": "resolution",
                "display_name": "Simulation Resolution (s)",
                "value": 1,
            }
        ]
