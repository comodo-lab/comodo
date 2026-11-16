import pytest

import src.spc_setup as spc

SPC_ID = "sensor-value--spc-output"
GAINS = {"k_p": 10.0, "k_i": 1.0, "k_d": 0.1, "k_aw": 0.05, "k_df": 0.01, "max_rate": None}
ROWS = [{"name": SPC_ID, **GAINS}]


class TestToSpcConfig:
    def test_groups_parameters_under_pid(self):
        assert spc.to_spc_config(ROWS) == {SPC_ID: {"pid": GAINS}}

    def test_max_rate(self):
        rows = [{"name": SPC_ID, **GAINS, "max_rate": 5}]
        assert spc.to_spc_config(rows)[SPC_ID]["pid"]["max_rate"] == 5.0

    def test_missing_max_rate_is_none(self):
        rows = [{"name": SPC_ID, **GAINS}]
        del rows[0]["max_rate"]
        assert spc.to_spc_config(rows)[SPC_ID]["pid"]["max_rate"] is None

    def test_ints_are_converted(self):
        pid = spc.to_spc_config([{"name": SPC_ID, **GAINS, "k_i": 1}])[SPC_ID]["pid"]
        assert isinstance(pid["k_i"], float)

    @pytest.mark.parametrize("value", [None, "", "2.5", "abc", True])
    def test_invalid_value_raises(self, value):
        rows = [{"name": SPC_ID, **GAINS, "k_d": value}]
        with pytest.raises(ValueError) as e:
            spc.to_spc_config(rows)
        assert f"Invalid Derivative for setpoint controller '{SPC_ID}': {value!r}" in str(
            e.value
        )

    def test_missing_value_raises(self):
        with pytest.raises(ValueError):
            spc.to_spc_config([{"name": SPC_ID, "k_p": 1.0}])

    def test_empty(self):
        assert spc.to_spc_config([]) == {}
        assert spc.to_spc_config(None) == {}
