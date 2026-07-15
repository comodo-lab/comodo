import yaml
import os


CONFIG_PATH = os.getenv("COMODO_CONFIG", "/app/comodo.yaml")


class ComodoConfig:
    def __init__(self, config_path=CONFIG_PATH):
        with open(config_path, "r") as f:
            self._raw = yaml.safe_load(f)
        self._instruments = self._raw.get("instruments", {})
        self._controllable = []
        self._param_dicts = []
        self._parse()

    def _parse(self):
        pid_targets = self._find_pid_targets()
        self._controllable = []
        self._all_controllable = []
        self._param_dicts = []
        self._all_param_dicts = []
        tracked_instruments = set()

        for inst_name, inst_config in self._instruments.items():
            variables = inst_config.get("variables", {})
            for var_name, var_config in variables.items():
                key = f"{inst_name}/{var_name}"

                if "actuator" in var_config:
                    act = var_config["actuator"]
                    entry = {
                        "name": key,
                        "min": act.get("min", 0),
                        "max": act.get("max", 100),
                        "step": 1,
                        "default_setpoint": act.get("default_setpoint", 0),
                    }
                    self._all_controllable.append(key)
                    self._all_param_dicts.append(entry)
                    tracked_instruments.add(inst_name)

                    if "setpoint_controller" not in var_config:
                        self._controllable.append(key)
                        self._param_dicts.append(entry)

                if key in pid_targets:
                    sensor = var_config.get("sensor", {})
                    entry = {
                        "name": key,
                        "min": sensor.get("min", 0),
                        "max": sensor.get("max", 100),
                        "step": 1,
                        "default_setpoint": sensor.get("default_setpoint", 0),
                    }
                    self._controllable.append(key)
                    self._param_dicts.append(entry)
                    self._all_controllable.append(key)
                    self._all_param_dicts.append(entry)
                    tracked_instruments.add(inst_name)

        for inst_name, inst_config in self._instruments.items():
            if inst_name in tracked_instruments:
                continue
            variables = inst_config.get("variables", {})
            for var_name, var_config in variables.items():
                if "sensor" in var_config:
                    self._all_param_dicts.append({"name": f"{inst_name}/{var_name}"})
                    break

    def _find_pid_targets(self):
        targets = set()
        for inst_config in self._instruments.values():
            variables = inst_config.get("variables", {})
            for var_config in variables.values():
                sc = var_config.get("setpoint_controller")
                if sc and "external_sensor" in sc:
                    ref = sc["external_sensor"]
                    targets.add(ref)
        return targets

    @property
    def pid_pairs(self):
        pairs = []
        for inst_name, inst_config in self._instruments.items():
            variables = inst_config.get("variables", {})
            for var_name, var_config in variables.items():
                sc = var_config.get("setpoint_controller")
                if sc and "external_sensor" in sc:
                    sensor = sc["external_sensor"]
                    actuator = f"{inst_name}/{var_name}"
                    pairs.append({"sensor": sensor, "actuator": actuator})
        return pairs

    @property
    def params(self):
        return list(self._controllable)

    @property
    def param_dicts(self):
        return list(self._param_dicts)

    @property
    def ini_data_dict(self):
        times = [0, 30, 60, 90, 120, 150, 180]
        defaults = {
            "furnace_centre/temperature": [150, 150, 150, 100, 50, 25, 0],
            "furnace_left/temperature":   [100, 100, 100,  67, 33, 17, 0],
            "furnace_right/temperature":  [100, 100, 100,  67, 33, 17, 0],
            "pressure_upstream/pressure": [5, 3.75, 2.5, 1.25, 0, 0, 0],
        }
        rows = []
        for i, t in enumerate(times):
            row = {"time": t}
            for p in self._controllable:
                row[p] = defaults.get(p, [0.0] * len(times))[i]
                row[f"{p}_profile"] = "linear"
            rows.append(row)
        return rows

    @property
    def default_setpoints(self):
        result = {}
        for entry in self._all_param_dicts:
            if "default_setpoint" in entry:
                inst_id = entry["name"].split("/")[0]
                result[inst_id] = entry["default_setpoint"]
        return result

    @property
    def ini_instrument_dict(self):
        result = []
        for entry in self._all_param_dicts:
            item = {"name": entry["name"], "tolerance": 1.0}
            if "default_setpoint" in entry:
                item["default_setpoint"] = entry["default_setpoint"]
            result.append(item)
        return result

    @property
    def ini_experiment_config(self):
        return [
            {"name": "resolution", "display_name": "Simulation Resolution (s)", "value": 1},
        ]
