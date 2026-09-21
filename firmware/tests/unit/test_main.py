import asyncio

import pytest
from unittest.mock import patch, call

from tests.conftest import (
    firmware_env,
    mock_state,
)

import main

pytestmark = pytest.mark.asyncio


class TestTimerFunctions:
    @pytest.fixture
    def timer_mocks(self, mock_state):
        with patch("main.asyncio.sleep") as mock_sleep:
            # asyncio.sleep raises CancelledError, to exit the infinite loops
            mock_sleep.side_effect = asyncio.CancelledError

            yield {
                "state": mock_state,
                "sleep": mock_sleep,
            }

    async def test_heartbeat_tick(self, timer_mocks):
        mock_istate = timer_mocks["state"]

        hb_task = asyncio.create_task(main.heartbeat_tick(mock_istate))
        with pytest.raises(asyncio.CancelledError):
            await hb_task

        mock_istate.publish_heartbeat.assert_called_once_with()
        timer_mocks["sleep"].assert_called_once_with(
            mock_istate.instrument.config["HEARTBEAT_INTERVAL"]
        )

    async def test_heartbeat_ticks_multiple_times(self, timer_mocks):
        mock_istate = timer_mocks["state"]
        timer_mocks["sleep"].side_effect = [None, asyncio.CancelledError]

        hb_task = asyncio.create_task(main.heartbeat_tick(mock_istate))
        with pytest.raises(asyncio.CancelledError):
            await hb_task

        assert mock_istate.publish_heartbeat.call_count == 2
        timer_mocks["sleep"].assert_has_calls(
            [
                call(mock_istate.instrument.config["HEARTBEAT_INTERVAL"]),
                call(mock_istate.instrument.config["HEARTBEAT_INTERVAL"]),
            ]
        )

    async def test_measurement_tick_value_ok(self, timer_mocks):
        mock_istate = timer_mocks["state"]
        mock_istate.status = "initialising"
        var_name = "temperature"
        m_interval = 1.0
        ready_event = asyncio.Event()
        mock_istate.instrument.measure_or_simulate.return_value = 1.3

        m_task = asyncio.create_task(
            main.measurement_tick(mock_istate, var_name, m_interval, ready_event)
        )
        with pytest.raises(asyncio.CancelledError):
            await m_task

        mock_istate.instrument.measure_or_simulate.assert_called_once_with(var_name)
        assert mock_istate.status == "initialising"
        mock_istate.client.publish.assert_called_once()
        timer_mocks["sleep"].assert_called_once_with(m_interval)
        assert ready_event.is_set()

    async def test_measurement_tick_with_None_value(self, timer_mocks):
        mock_istate = timer_mocks["state"]
        mock_istate.status = "initialising"
        var_name = "temperature"
        m_interval = 1.0
        ready_event = asyncio.Event()
        mock_istate.instrument.measure_or_simulate.return_value = None

        m_task = asyncio.create_task(
            main.measurement_tick(mock_istate, var_name, m_interval, ready_event)
        )
        with pytest.raises(asyncio.CancelledError):
            await m_task

        mock_istate.instrument.measure_or_simulate.assert_called_once_with(var_name)
        assert mock_istate.status == "error"
        mock_istate.client.publish.assert_called_once()
        timer_mocks["sleep"].assert_called_once_with(m_interval)
        assert ready_event.is_set()

    async def test_measurement_tick_ready_on_first_measurement_only(self, timer_mocks):
        mock_istate = timer_mocks["state"]
        var_name = "temperature"
        m_interval = 1.0
        ready_event = asyncio.Event()
        mock_istate.instrument.measure_or_simulate.return_value = 1.3
        timer_mocks["sleep"].side_effect = [None, asyncio.CancelledError]

        with patch.object(ready_event, "set", wraps=ready_event.set) as set_ready:
            m_task = asyncio.create_task(
                main.measurement_tick(mock_istate, var_name, m_interval, ready_event)
            )
            with pytest.raises(asyncio.CancelledError):
                await m_task

        mock_istate.instrument.measure_or_simulate.assert_has_calls(
            [call(var_name), call(var_name)]
        )
        assert mock_istate.instrument.measure_or_simulate.call_count == 2
        assert mock_istate.client.publish.call_count == 2
        timer_mocks["sleep"].assert_has_calls([call(m_interval), call(m_interval)])
        set_ready.assert_called_once_with()
        assert ready_event.is_set()


class TestSensorInitialisation:
    @pytest.fixture
    def si_mocks(self, mock_state):
        measurement_calls = []
        sensor_ready_events = {}

        async def mock_measurement_tick(istate, variable, interval, ready_event):
            measurement_calls.append((istate, variable, interval))
            sensor_ready_events[variable] = ready_event
            ready_event.set()
            await asyncio.Future()

        async def never_ready_tick(_istate, _variable, _interval, _ready_event):
            await asyncio.Future()

        with patch.object(main, "measurement_tick", mock_measurement_tick):
            yield {
                "state": mock_state,
                "measurement_calls": measurement_calls,
                "sensor_ready_events": sensor_ready_events,
                "never_ready_tick": never_ready_tick,
            }

    async def test_start_sensors_measurements_waits_for_all_sensors(self, si_mocks):
        mock_istate = si_mocks["state"]
        mock_istate.instrument.config["MEASUREMENT_INTERVALS"] = {
            "temperature": 1.0,
            "pressure": 2.0,
        }
        instrument_ready_event = asyncio.Event()
        task = asyncio.create_task(
            main.start_sensors_measurements(
                mock_istate, instrument_ready_event, timeout=1.0
            )
        )
        await asyncio.wait_for(instrument_ready_event.wait(), timeout=1.0)

        assert si_mocks["measurement_calls"] == [
            (mock_istate, "temperature", 1.0),
            (mock_istate, "pressure", 2.0),
        ]
        assert all(event.is_set() for event in si_mocks["sensor_ready_events"].values())

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_start_sensors_measurements_rejects_empty_configuration(
        self, si_mocks
    ):
        mock_istate = si_mocks["state"]
        mock_istate.instrument.config["MEASUREMENT_INTERVALS"] = {}

        with pytest.raises(RuntimeError, match="No sensors configured"):
            await main.start_sensors_measurements(
                mock_istate, asyncio.Event(), timeout=1.0
            )

    async def test_start_sensors_measurements_times_out(self, si_mocks):
        with patch.object(main, "measurement_tick", si_mocks["never_ready_tick"]):
            mock_istate = si_mocks["state"]
            mock_istate.instrument.config["MEASUREMENT_INTERVALS"] = {
                "temperature": 1.0
            }
            with pytest.raises(ExceptionGroup) as exc_info:
                await main.start_sensors_measurements(
                    mock_istate, asyncio.Event(), timeout=0.01
                )

        assert len(exc_info.value.exceptions) == 1
        assert isinstance(exc_info.value.exceptions[0], RuntimeError)
        assert (
            str(exc_info.value.exceptions[0]) == "Sensors failed to initialise in time"
        )
