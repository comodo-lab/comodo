import json
import pytest
from unittest.mock import patch, MagicMock

from utils.tests.mocks.mock_mqtt_clients import (
    pytest_runtest_makereport,
    InMemoryMessageBus,
    message_bus,
    mqtt_mocks,
)

from src.instrument import BaseInstrument


@pytest.fixture(autouse=True)
def get_env():
    return {
        "INSTRUMENT_NAME": "test",
        "FIRMWARE": "test_instrument",
        "ADDRESS": "1.2.3.4",
        "ACTIVE_VARIABLES": '["temperature","pressure"]',
        "HEARTBEAT_INTERVAL": "1000",
        "INTERVAL_TEMPERATURE": "1000",
        "INTERVAL_PRESSURE": "1000",
        "SIMULATE": "True",
    }


@pytest.fixture
def test_instrument():

    driver = MagicMock(spec=BaseInstrument)
    driver.available_variables = {
        "temperature": {
            "sensor": "T",
        },
        "pressure": {
            "sensor": "P",
            "actuator": "P",
        },
    }
    driver._simulated = {}

    def get_measurement(state, variable):
        driver._simulated[variable] = driver._simulated.get(variable, 0) + 1
        return float(driver._simulated[variable])

    driver.get_measurement.side_effect = get_measurement

    with patch("src.instrument.BaseInstrument.create_instrument", return_value=driver):
        yield driver
