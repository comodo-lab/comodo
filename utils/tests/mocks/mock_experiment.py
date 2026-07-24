import pytest


@pytest.fixture
def mock_experiment_dict():
    """Fixture that returns a valid experiment configuration dictionary."""
    data = {
        "id": "123",
        "config": {"resolution": 2},
        "experiment_definition": [
            {"time": 0, "furnace/temperature": 25, "pressure/pressure": 1},
            {"time": 4, "furnace/temperature": 25, "pressure/pressure": 150},
            {"time": 6, "furnace/temperature": 500, "pressure/pressure": 150},
            {"time": 10, "furnace/temperature": 500, "pressure/pressure": 1},
            {"time": 12, "furnace/temperature": 25, "pressure/pressure": 1},
        ],
    }
    return data


@pytest.fixture
def mock_setpoints():
    """Fixture that returns a list of setpoints as expected from split_setpoints."""
    return [
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 75.5},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 150},
        {"duration": 2, "furnace/temperature": 500, "pressure/pressure": 150},
        {"duration": 2, "furnace/temperature": 500, "pressure/pressure": 75.5},
        {"duration": 2, "furnace/temperature": 500, "pressure/pressure": 1},
        {"duration": 2, "furnace/temperature": 25, "pressure/pressure": 1},
    ]
