from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    firmware_env,
    mock_load_config,
    expected_config,
)

import src.instrument as instrument


class TestCreateInstrument:
    @pytest.fixture
    def ci_mocks(self, firmware_env):
        with (
            patch("src.instrument.GenericInstrument") as mock_generic_instrument_class,
            patch("src.instrument.importlib.import_module") as mock_import_module,
        ):
            mock_generic_instrument_class.return_value = MagicMock()
            module = MagicMock()
            instrument_class = MagicMock()
            instrument = MagicMock()
            instrument_class.return_value = instrument
            module.Instrument = instrument_class
            mock_import_module.return_value = module
            yield {
                "mock_config": mock_load_config(firmware_env),
                "mock_generic_instrument_class": mock_generic_instrument_class,
                "mock_import_module": mock_import_module,
                "mock_module": module,
                "mock_instrument_class": instrument_class,
                "mock_instrument": instrument,
            }

    def test_no_firmware_returns_generic_instrument(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = None
        ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_called_once_with(mock_config)
        assert ins == ci_mocks["mock_generic_instrument_class"].return_value
        ci_mocks["mock_import_module"].assert_not_called()

    def test_generic_instrument(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "generic_instrument"
        ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_called_once_with(mock_config)
        assert ins == ci_mocks["mock_generic_instrument_class"].return_value
        ci_mocks["mock_import_module"].assert_not_called()

    def test_missing_module(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "something_nonexistent"

        err = ModuleNotFoundError("Module not found")
        err.name = "src.instruments.something_nonexistent"
        ci_mocks["mock_import_module"].side_effect = err

        with pytest.raises(ValueError) as e:
            ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_not_called()
        ci_mocks["mock_import_module"].assert_called_once_with(
            "src.instruments.something_nonexistent"
        )
        assert "ins" not in locals()
        assert "Unknown instrument plugin: something_nonexistent" in str(e.value)
        ci_mocks["mock_module"].Instrument.assert_not_called()

    def test_sub_import_error(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "something_nonexistent"

        err = ModuleNotFoundError("Module not found")
        err.name = "sub.import.not.found"
        ci_mocks["mock_import_module"].side_effect = err

        with pytest.raises(ModuleNotFoundError) as e:
            ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_not_called()
        ci_mocks["mock_import_module"].assert_called_once_with(
            "src.instruments.something_nonexistent"
        )
        assert "ins" not in locals()
        assert "Module not found" in str(e.value)
        ci_mocks["mock_module"].Instrument.assert_not_called()

    def test_instrument_class_not_defined(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "for_sure_exists"

        del ci_mocks["mock_module"].Instrument  # Remove Instrument class from mock

        with pytest.raises(ValueError) as e:
            ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_not_called()
        ci_mocks["mock_import_module"].assert_called_once_with(
            "src.instruments.for_sure_exists"
        )
        assert "ins" not in locals()
        assert (
            "Instrument plugin 'for_sure_exists' does not have an 'Instrument' class"
            in str(e.value)
        )

    def test_instrument_instantiation_error(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "for_sure_exists"

        ci_mocks["mock_instrument_class"].side_effect = Exception("Some other error")

        with pytest.raises(Exception) as e:
            ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_not_called()
        ci_mocks["mock_import_module"].assert_called_once_with(
            "src.instruments.for_sure_exists"
        )
        ci_mocks["mock_instrument_class"].assert_called_once_with(mock_config)
        assert "ins" not in locals()
        assert "Some other error" in str(e.value)

    def test_all_ok(self, ci_mocks):
        mock_config = ci_mocks["mock_config"]
        mock_config["FIRMWARE"] = "for_sure_exists"

        ins = instrument.create_instrument(mock_config)

        ci_mocks["mock_generic_instrument_class"].assert_not_called()
        ci_mocks["mock_import_module"].assert_called_once_with(
            "src.instruments.for_sure_exists"
        )
        ci_mocks["mock_instrument_class"].assert_called_once_with(mock_config)
        assert ins == ci_mocks["mock_instrument"]


class TestBaseInstrument:
    @pytest.fixture
    def bi_mocks(self, firmware_env):
        class ConcreteInstrument(instrument.BaseInstrument):
            def initialise(self):
                pass

            def simulate(self, _variable):
                return 0

            def get_measurement(self, _variable):
                return 0

            def go_to_setpoint(self, _variable, _setpoint):
                pass

        with (
            patch.object(ConcreteInstrument, "initialise") as mock_initialise,
            patch.object(ConcreteInstrument, "simulate") as mock_simulate,
            patch.object(ConcreteInstrument, "get_measurement") as mock_get_measurement,
            patch.object(ConcreteInstrument, "go_to_setpoint") as mock_go_to_setpoint,
        ):
            yield {
                "environment": firmware_env,
                "ConcreteInstrument": ConcreteInstrument,
                "mock_config": mock_load_config(firmware_env),
                "mock_initialise": mock_initialise,
                "mock_simulate": mock_simulate,
                "mock_get_measurement": mock_get_measurement,
                "mock_go_to_setpoint": mock_go_to_setpoint,
            }

    def test_incomplete_subclass(self, bi_mocks):
        class IncompleteInstrument(instrument.BaseInstrument):
            def something(self):
                pass

        with pytest.raises(TypeError) as e:
            ins = IncompleteInstrument(bi_mocks["mock_config"])

        assert "Can't instantiate abstract class IncompleteInstrument" in str(e.value)
        assert "initialise" in str(e.value)
        assert "simulate" in str(e.value)
        assert "get_measurement" in str(e.value)
        assert "go_to_setpoint" in str(e.value)
        assert "ins" not in locals()

    def test_init(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]

        ins = bi_mocks["ConcreteInstrument"](mock_config)

        assert ins.config == mock_config
        assert ins.setpoints == {var: None for var in mock_config["DEFAULT_SETPOINTS"]}
        assert ins.previous_measurements == {}
        bi_mocks["mock_initialise"].assert_called_once_with()

    def test_default_sim_no_setpoint(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]

        ins = bi_mocks["ConcreteInstrument"](mock_config)
        # No previous measurement and no setpoint should return 0
        result = ins.default_sim("some_variable")
        assert result == 0
        # If previous measurement is set but no setpoint, it should return the previous measurement
        ins.previous_measurements["some_variable"] = 10
        result = ins.default_sim("some_variable")
        assert result == 10

    def test_default_sim_with_setpoint(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]

        ins = bi_mocks["ConcreteInstrument"](mock_config)
        ins.setpoints["some_variable"] = 20
        # No previous measurement, should return (20-0)/2
        result = ins.default_sim("some_variable")
        assert result == 10
        # If previous measurement is set, should get half way there
        ins.previous_measurements["some_variable"] = 10
        result = ins.default_sim("some_variable")
        assert result == 15

    def test_measure_or_simulate_undefined_variable(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        assert ins.previous_measurements == {}

        with pytest.raises(ValueError) as e:
            result = ins.measure_or_simulate("undefined_variable")

        assert "Cannot measure 'undefined_variable'" in str(e.value)
        assert "Variable not available" in str(e.value)
        bi_mocks["mock_simulate"].assert_not_called()
        bi_mocks["mock_get_measurement"].assert_not_called()
        assert "result" not in locals()

    def test_measure_or_simulate_simualting(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        mock_config["SIMULATE"] = True
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        ins.available_variables = {"some_variable": {}}
        new_measurement = 42.0
        bi_mocks["mock_simulate"].return_value = new_measurement
        assert ins.previous_measurements == {}

        result = ins.measure_or_simulate("some_variable")

        assert result == new_measurement
        assert ins.previous_measurements["some_variable"] == new_measurement
        bi_mocks["mock_simulate"].assert_called_once_with("some_variable")
        bi_mocks["mock_get_measurement"].assert_not_called()

    def test_measure_or_simulate_getting_measurement(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        mock_config["SIMULATE"] = False
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        ins.available_variables = {"some_variable": {}}
        new_measurement = 42.42
        bi_mocks["mock_get_measurement"].return_value = new_measurement
        assert ins.previous_measurements == {}

        result = ins.measure_or_simulate("some_variable")

        assert result == new_measurement
        assert ins.previous_measurements["some_variable"] == new_measurement
        bi_mocks["mock_simulate"].assert_not_called()
        bi_mocks["mock_get_measurement"].assert_called_once_with("some_variable")

    def test_set_and_go_to_setpoint_undefined_variable(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        new_setpoint = 10.0
        assert ins.setpoints.get("undefined_variable") == None

        with pytest.raises(ValueError) as e:
            ins.set_and_go_to_setpoint("undefined_variable", new_setpoint)

        assert "Cannot set setpoint for 'undefined_variable'" in str(e.value)
        assert "Variable not available" in str(e.value)
        assert ins.setpoints.get("undefined_variable") == None
        bi_mocks["mock_go_to_setpoint"].assert_not_called()

    def test_set_and_go_to_setpoint_simulating(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        mock_config["SIMULATE"] = True
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        ins.available_variables = {"some_variable": {}}
        new_setpoint = 10.0
        assert ins.setpoints.get("some_variable") == None

        ins.set_and_go_to_setpoint("some_variable", new_setpoint)

        assert ins.setpoints.get("some_variable") == new_setpoint
        bi_mocks["mock_go_to_setpoint"].assert_not_called()

    def test_set_and_go_to_setpoint_not_simulating(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        mock_config["SIMULATE"] = False
        ins = bi_mocks["ConcreteInstrument"](mock_config)
        ins.available_variables = {"some_variable": {}}
        new_setpoint = 10.0
        assert ins.setpoints.get("some_variable") == None

        ins.set_and_go_to_setpoint("some_variable", new_setpoint)

        assert ins.setpoints.get("some_variable") == new_setpoint
        bi_mocks["mock_go_to_setpoint"].assert_called_once_with(
            "some_variable", new_setpoint
        )

    def test_print_config(self, bi_mocks):
        mock_config = bi_mocks["mock_config"]
        ins = bi_mocks["ConcreteInstrument"](mock_config)

        result = ins.print_config()

        assert result == expected_config(bi_mocks["environment"])
