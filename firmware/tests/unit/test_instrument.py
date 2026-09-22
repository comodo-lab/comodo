from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    firmware_env,
    mock_load_config,
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
