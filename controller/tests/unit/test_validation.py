import json
import pytest
from unittest.mock import MagicMock, mock_open, patch
from jsonschema import ValidationError

from src.validation import (
    ValidationException,
    validate_file,
    validate_file_print_errors,
    validate_file_soft,
    validate_dict,
)


# =============== Fixtures ===============


@pytest.fixture
def validate_mocks():
    with patch("builtins.open") as mock_open_func, patch(
        "src.validation.json.load"
    ) as mock_json_load, patch(
        "src.validation.jsonschema.validate"
    ) as mock_jsonschema_validate:
        loaded_contents = []

        def side_effect_load(file_obj, **kwargs):
            content = file_obj.read()
            loaded_contents.append(content)
            return json.loads(content, **kwargs)

        mock_json_load.side_effect = side_effect_load
        yield {
            "open": mock_open_func,
            "json_load": mock_json_load,
            "json_load_calls": loaded_contents,
            "jsonschema_validate": mock_jsonschema_validate,
        }


# ========================================


class TestValidateFile:

    @pytest.fixture
    def vf_mocks(self):
        with patch("builtins.open") as mock_open_func, patch(
            "src.validation.json.load"
        ) as mock_json_load, patch(
            "src.validation.jsonschema.validate"
        ) as mock_jsonschema_validate:
            loaded_contents = []

            def side_effect_load(file_obj, **kwargs):
                content = file_obj.read()
                loaded_contents.append(content)
                return json.loads(content, **kwargs)

            mock_json_load.side_effect = side_effect_load
            yield {
                "open": mock_open_func,
                "json_load": mock_json_load,
                "json_load_calls": loaded_contents,
                "jsonschema_validate": mock_jsonschema_validate,
            }

    def test_schema_not_found(self, vf_mocks):
        vf_mocks["open"].side_effect = FileNotFoundError()
        with pytest.raises(ValidationException) as e:
            validate_file("some_file.json", "non_existent_schema.json")

        assert "Error: File not found - non_existent_schema.json" in e.value.args
        vf_mocks["json_load"].assert_not_called()
        vf_mocks["jsonschema_validate"].assert_not_called()

    def test_invalid_schema(self, vf_mocks):
        vf_mocks["open"].side_effect = (
            mock_open(read_data="{ invalid json ").return_value,
        )
        with pytest.raises(ValidationException) as e:
            validate_file("some_file.json", "invalid_schema.json")

        assert "Error decoding JSON: invalid_schema.json" in e.value.args[0]
        # Should have tried to load schema only
        vf_mocks["json_load"].assert_called_once()
        assert vf_mocks["json_load_calls"][0] == "{ invalid json "
        vf_mocks["jsonschema_validate"].assert_not_called()

    def test_file_not_found(self, vf_mocks):
        vf_mocks["open"].side_effect = [
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
            FileNotFoundError(),  # File to validate not found
        ]
        with pytest.raises(ValidationException) as e:
            validate_file("non_existent_file.json", "some_schema.json")

        assert "Error: File not found - non_existent_file.json" in e.value.args[0]
        # Should have loaded schema, but not the file
        vf_mocks["json_load"].assert_called_once()
        assert vf_mocks["json_load_calls"][0] == '{"s": "s"}'
        vf_mocks["jsonschema_validate"].assert_not_called()

    def test_invalid_file(self, vf_mocks):
        vf_mocks["open"].side_effect = [
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
            mock_open(read_data="{ invalid json ").return_value,  # Invalid file
        ]
        with pytest.raises(ValidationException) as e:
            validate_file("invalid_file.json", "some_schema.json")

        assert "Error decoding JSON: invalid_file.json" in e.value.args[0]
        # Should have loaded schema, and tried to load the file
        vf_mocks["json_load"].call_count == 2
        assert vf_mocks["json_load_calls"][0] == '{"s": "s"}'
        assert vf_mocks["json_load_calls"][1] == "{ invalid json "
        vf_mocks["jsonschema_validate"].assert_not_called()

    def test_validation_errors(self, vf_mocks):
        vf_mocks["open"].side_effect = [
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
            mock_open(read_data='{"e": 123}').return_value,  # File loads ok
        ]
        vf_mocks["jsonschema_validate"].side_effect = ValidationError("Some error")
        with patch("jsonschema.Draft7Validator") as mock_validator:
            mvc = MagicMock()
            mvc.iter_errors.return_value = [
                MagicMock(json_path="$.a", message="Invalid here"),
                MagicMock(json_path="$.b", message="Invalid there"),
            ]
            mock_validator.return_value = mvc
            with pytest.raises(ValidationException) as e:
                validate_file("invalid_data.json", "simple_schema.json")

        assert "Validation errors:" in e.value.args[0]
        assert "$.a -> Invalid here" in e.value.args[0]
        assert "$.b -> Invalid there" in e.value.args[0]
        # Should have loaded both schema and file
        vf_mocks["json_load"].call_count == 2
        assert vf_mocks["json_load_calls"][0] == '{"s": "s"}'
        assert vf_mocks["json_load_calls"][1] == '{"e": 123}'

    def test_validation_passes(self, vf_mocks):
        vf_mocks["open"].side_effect = [
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
            mock_open(read_data='{"e": 123}').return_value,  # File loads ok
        ]
        result = validate_file("valid_data.json", "simple_schema.json")

        assert result == {"e": 123}
        # Should have loaded both schema and file
        vf_mocks["json_load"].call_count == 2
        assert vf_mocks["json_load_calls"][0] == '{"s": "s"}'
        assert vf_mocks["json_load_calls"][1] == '{"e": 123}'
        # Should have called validate without errors
        vf_mocks["jsonschema_validate"].assert_called_once_with(
            instance={"e": 123}, schema={"s": "s"}
        )


class SecondaryValidators:
    @pytest.fixture
    def sv_mocks(self):
        with patch("src.validation.validate_file") as mock_validate, patch(
            "builtins.print"
        ) as mock_print, patch("builtins.exit") as mock_exit:
            yield {
                "validate_file": mock_validate,
                "print": mock_print,
                "exit": mock_exit,
            }

    def test_validate_file_print_errors_fails(self, sv_mocks):
        sv_mocks["validate_file"].side_effect = ValidationException(
            "Some validation error"
        )
        validate_file_print_errors("some_file.json", "some_schema.json")

        sv_mocks["print"].assert_called_once_with("Some validation error")
        assert "Some validation error" in sv_mocks["print"].call_args[0][0]
        sv_mocks["exit"].assert_called_once_with(1)

    def test_validate_file_print_errors_passes(self, sv_mocks):
        sv_mocks["validate_file"].return_value = {"valid": True}
        result = validate_file_print_errors("some_file.json", "some_schema.json")

        assert result == {"valid": True}
        sv_mocks["print"].assert_not_called()
        sv_mocks["exit"].assert_not_called()

    def test_validate_file_soft_fails(self, sv_mocks):
        sv_mocks["validate_file"].side_effect = ValidationException(
            "Some validation error"
        )
        result, err = validate_file_soft("some_file.json", "some_schema.json")

        assert result is None
        assert err == "Some validation error"
        sv_mocks["print"].assert_not_called()
        sv_mocks["exit"].assert_not_called()

    def test_validate_file_soft_passes(self, sv_mocks):
        sv_mocks["validate_file"].return_value = {"valid": True}
        result, err = validate_file_soft("some_file.json", "some_schema.json")

        assert result == {"valid": True}
        assert err is None
        sv_mocks["print"].assert_not_called()
        sv_mocks["exit"].assert_not_called()


class TestValidateDict:

    def test_schema_not_found(self, validate_mocks):
        validate_mocks["open"].side_effect = FileNotFoundError()
        with pytest.raises(ValidationException) as e:
            validate_dict({"some": "d", "to": "val"}, "non_existent_schema.json")

        assert "Error: File not found - non_existent_schema.json" in e.value.args
        validate_mocks["json_load"].assert_not_called()
        validate_mocks["jsonschema_validate"].assert_not_called()

    def test_invalid_schema(self, validate_mocks):
        validate_mocks["open"].side_effect = (
            mock_open(read_data="{ invalid json ").return_value,
        )
        with pytest.raises(ValidationException) as e:
            validate_dict({"some": "d", "to": "val"}, "invalid_schema.json")

        assert "Error decoding JSON: invalid_schema.json" in e.value.args[0]
        # Should have tried to load schema
        validate_mocks["json_load"].assert_called_once()
        assert validate_mocks["json_load_calls"][0] == "{ invalid json "
        validate_mocks["jsonschema_validate"].assert_not_called()

    def test_validation_errors(self, validate_mocks):
        validate_mocks["open"].side_effect = (
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
        )
        validate_mocks["jsonschema_validate"].side_effect = ValidationError(
            "Some error"
        )
        with patch("jsonschema.Draft7Validator") as mock_validator:
            mvc = MagicMock()
            mvc.iter_errors.return_value = [
                MagicMock(json_path="$.a", message="Invalid here"),
                MagicMock(json_path="$.b", message="Invalid there"),
            ]
            mock_validator.return_value = mvc
            with pytest.raises(ValidationException) as e:
                validate_dict({"some": "d", "to": "val"}, "simple_schema.json")

        assert "Validation errors:" in e.value.args[0]
        assert "$.a -> Invalid here" in e.value.args[0]
        assert "$.b -> Invalid there" in e.value.args[0]
        # Should have loaded both schema and file
        validate_mocks["json_load"].call_count == 1
        assert validate_mocks["json_load_calls"][0] == '{"s": "s"}'

    def test_validation_passes(self, validate_mocks):
        validate_mocks["open"].side_effect = [
            mock_open(read_data='{"s": "s"}').return_value,  # Schema loads ok
        ]
        result = validate_dict({"some": "d", "to": "val"}, "simple_schema.json")

        assert result == {"some": "d", "to": "val"}
        # Should have loaded both schema and file
        validate_mocks["json_load"].call_count == 1
        assert validate_mocks["json_load_calls"][0] == '{"s": "s"}'
        # Should have called validate without errors
        validate_mocks["jsonschema_validate"].assert_called_once_with(
            instance={"some": "d", "to": "val"}, schema={"s": "s"}
        )
