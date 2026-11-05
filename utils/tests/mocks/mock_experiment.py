import pytest


@pytest.fixture
def mock_experiment_dict():
    """Fixture that returns a valid experiment configuration dictionary."""
    data = {
        "temp_id": "123",
        "config": {
            "resolution": 2,
            "instruments": {
                "furnace": {"temperature": {"tolerance": 5, "offset": 273}},
                "pressure": {"pressure": {"tolerance": 0.2}},
                "mass_flow": {"mass_flow": {"tolerance": 1}},
            },
            "spcs": {
                "pressure-pressure--mass_flow-mass_flow": {
                    "pid": {
                        "k_p": 10.0,
                        "k_i": 1.0,
                        "k_d": 0.1,
                        "k_aw": 0.05,
                        "k_df": 0.01,
                        "max_rate": None,
                    }
                },
            },
        },
        "experiment_definition": [
            {"time": 0, "furnace/temperature": 25, "pressure/pressure": 1},
            {"time": 4, "furnace/temperature": 25, "pressure/pressure": 1.50},
            {"time": 6, "furnace/temperature": 50, "pressure/pressure": 1.50},
            {"time": 10, "furnace/temperature": 50, "pressure/pressure": 1},
            {"time": 12, "furnace/temperature": 25, "pressure/pressure": 1},
        ],
    }
    return data


@pytest.fixture
def mock_setpoints():
    """Fixture that returns a list of setpoints as expected from split_setpoints."""
    return [
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1.25},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1.50},
        {"duration": 2, "furnace/temperature": 50, "pressure/pressure": 1.50},
        {"duration": 2, "furnace/temperature": 50, "pressure/pressure": 1.25},
        {"duration": 2, "furnace/temperature": 50, "pressure/pressure": 1},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1},
    ]
