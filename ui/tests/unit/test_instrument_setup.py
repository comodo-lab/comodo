import os
import sys

import pytest
from dash.exceptions import PreventUpdate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
import instrument_setup as ins


class TestParseValue:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("273", 273),
            ("1.5", 1.5),
            ("true", True),
            ("[1, 2]", [1, 2]),
            ('{"a": 1}', {"a": 1}),
            ("text", "text"),
            ("", ""),
            (2.5, 2.5),
            (None, None),
        ],
    )
    def test_parse_value(self, value, expected):
        assert ins.parse_value(value) == expected


class TestToInstrumentConfig:
    def test_groups_rows_per_instrument_and_variable(self):
        rows = [
            {"name": "furnace/temperature", "key": "tolerance", "value": 1},
            {"name": "furnace", "key": "offset", "value": "273"},
            {"name": "pressure/pressure", "key": "tolerance", "value": "0.5"},
            {"name": "furnace/temperature", "key": "gain", "value": "fast"},
        ]
        assert ins.to_instrument_config(rows) == {
            "furnace": {
                "temperature": {"tolerance": 1, "gain": "fast"},
                "offset": 273,
            },
            "pressure": {"pressure": {"tolerance": 0.5}},
        }

    def test_ignores_rows_without_name_or_key(self):
        rows = [
            {"name": "", "key": "", "value": ""},
            {"name": "furnace", "key": " ", "value": 1},
            {"name": None, "key": "offset", "value": 1},
        ]
        assert ins.to_instrument_config(rows) == {}

    def test_strips_names_and_keys(self):
        rows = [{"name": " furnace ", "key": " offset ", "value": 1}]
        assert ins.to_instrument_config(rows) == {"furnace": {"offset": 1}}

    def test_no_rows(self):
        assert ins.to_instrument_config(None) == {}

    def test_key_and_variable_with_same_name(self):
        rows = [
            {"name": "furnace", "key": "temperature", "value": 1},
            {"name": "furnace/temperature", "key": "tolerance", "value": 1},
        ]
        with pytest.raises(ValueError, match="both a 'temperature' key and variable"):
            ins.to_instrument_config(rows)


class TestAddDeleteRows:
    ROWS = [
        {"name": "furnace/temperature", "key": "tolerance", "value": 1},
        {"name": "furnace", "key": "offset", "value": 273},
    ]

    def test_add_row(self):
        assert ins.add_row(1, self.ROWS) == self.ROWS + [
            {"name": "", "key": "", "value": ""}
        ]

    def test_add_row_not_clicked(self):
        with pytest.raises(PreventUpdate):
            ins.add_row(0, self.ROWS)

    def test_delete_selected(self):
        assert ins.delete_selected(1, [self.ROWS[0]], self.ROWS) == [self.ROWS[1]]

    def test_delete_nothing_selected(self):
        assert ins.delete_selected(1, None, self.ROWS) == self.ROWS
