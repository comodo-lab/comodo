import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config_loader import ComodoConfig


class TestColumnDataConsistency:
    """Regression tests for the table display bug.

    The original bug: main_window.py had its own PARAMS list with a typo
    ('pressure_upsteam' instead of 'pressure_upstream'). This caused AG Grid
    column field names to not match the data keys, resulting in empty cells.
    """

    def _get_column_fields(self, params):
        """Reproduce the column field generation logic from main_window.py."""
        columns = ["time"]
        for col in params:
            columns.append(col)
            columns.append(f"{col}_profile")
        return set(columns)

    def test_column_fields_match_data_keys(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        column_fields = self._get_column_fields(config.params)
        data = config.ini_data_dict

        for row in data:
            for key in row:
                if key == "id":
                    continue
                assert key in column_fields, (
                    f"Data key '{key}' has no matching column field. "
                    f"Available columns: {column_fields}"
                )

    def test_column_fields_match_data_keys_with_pid(self, sample_config_with_pid):
        config = ComodoConfig(sample_config_with_pid)
        column_fields = self._get_column_fields(config.params)
        data = config.ini_data_dict

        for row in data:
            for key in row:
                if key == "id":
                    continue
                assert key in column_fields, (
                    f"Data key '{key}' has no matching column field. "
                    f"Available columns: {column_fields}"
                )

    def test_profile_columns_exist(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        column_fields = self._get_column_fields(config.params)
        for param in config.params:
            assert f"{param}_profile" in column_fields

    def test_no_duplicate_columns(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        columns = ["time"]
        for col in config.params:
            columns.append(col)
            columns.append(f"{col}_profile")
        assert len(columns) == len(set(columns)), "Duplicate column names detected"

    def test_real_config_consistency(self):
        """Integration test: real comodo.yaml columns match data keys."""
        real_path = os.path.join(os.path.dirname(__file__), "../../../comodo.yaml")
        if not os.path.exists(real_path):
            pytest.skip("comodo.yaml not found at repo root")
        config = ComodoConfig(real_path)
        column_fields = self._get_column_fields(config.params)
        data = config.ini_data_dict
        for row in data:
            for key in row:
                if key == "id":
                    continue
                assert key in column_fields, (
                    f"Data key '{key}' has no matching column field"
                )
