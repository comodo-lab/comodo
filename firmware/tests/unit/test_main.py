import asyncio
import inspect

import pytest
from unittest.mock import ANY, call, patch, MagicMock

from tests.conftest import (
    firmware_env,
    mock_state,
)

import main


@pytest.mark.asyncio
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


@pytest.mark.asyncio
class TestStartSensorMeasurements:
    @pytest.fixture
    def ssm_mocks(self, mock_state):
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

    async def test_start_sensors_measurements_waits_for_all_sensors(self, ssm_mocks):
        mock_istate = ssm_mocks["state"]
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

        assert ssm_mocks["measurement_calls"] == [
            (mock_istate, "temperature", 1.0),
            (mock_istate, "pressure", 2.0),
        ]
        assert all(
            event.is_set() for event in ssm_mocks["sensor_ready_events"].values()
        )

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_start_sensors_measurements_rejects_empty_configuration(
        self, ssm_mocks
    ):
        mock_istate = ssm_mocks["state"]
        mock_istate.instrument.config["MEASUREMENT_INTERVALS"] = {}

        with pytest.raises(RuntimeError, match="No sensors configured"):
            await main.start_sensors_measurements(
                mock_istate, asyncio.Event(), timeout=1.0
            )

    async def test_start_sensors_measurements_times_out(self, ssm_mocks):
        with patch.object(main, "measurement_tick", ssm_mocks["never_ready_tick"]):
            mock_istate = ssm_mocks["state"]
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


@pytest.mark.asyncio
class TestStartInstrument:
    @pytest.fixture
    def si_mocks(self, mock_state):
        with (
            patch("main.config") as mock_config_module,
            patch("main.state") as mock_state_module,
            patch.object(main, "start_sensors_measurements") as mock_start_sensors,
            patch.object(main, "heartbeat_tick") as mock_heartbeat_tick,
        ):
            mock_config_module.load_config.return_value = mock_state.instrument.config
            mock_state_module.InstrumentState.return_value = mock_state

            async def completed_task(*_args, **_kwargs):
                return None

            mock_start_sensors.side_effect = completed_task
            mock_heartbeat_tick.side_effect = completed_task

            yield {
                "state": mock_state,
                "config_module": mock_config_module,
                "state_module": mock_state_module,
                "start_sensors": mock_start_sensors,
                "heartbeat_tick": mock_heartbeat_tick,
            }

    async def test_main_all_ok(self, si_mocks, capsys):
        mock_istate = si_mocks["state"]
        result = await main.start_instrument()

        si_mocks["config_module"].load_config.assert_called_once_with()
        si_mocks["state_module"].InstrumentState.assert_called_once_with(
            mock_istate.instrument.config
        )
        si_mocks["start_sensors"].assert_called_once_with(mock_istate, ANY, timeout=10)
        mock_istate.reset.assert_called_once_with()
        captured = capsys.readouterr()
        assert (
            "Instrument test_instrument created successfully using firmware "
            "generic_instrument" in captured.out
        )
        si_mocks["heartbeat_tick"].assert_called_once_with(mock_istate)
        assert result == 0

    async def test_main_propagates_sensor_initialisation_timeout(self, si_mocks):
        async def failed_start(*_args, **_kwargs):
            raise RuntimeError("Sensors failed to initialise in time")

        si_mocks["start_sensors"].side_effect = failed_start

        with pytest.raises(RuntimeError, match="Sensors failed to initialise in time"):
            await main.start_instrument()

        si_mocks["start_sensors"].assert_called_once_with(
            si_mocks["state"], ANY, timeout=10
        )
        si_mocks["state"].reset.assert_not_called()
        si_mocks["heartbeat_tick"].assert_not_called()

    async def test_main_propagates_other_sensor_initialisation_errors(self, si_mocks):
        error = ValueError("Instrument configuration is invalid")

        async def failed_start(*_args, **_kwargs):
            raise error

        si_mocks["start_sensors"].side_effect = failed_start

        with pytest.raises(ValueError, match="Instrument configuration is invalid"):
            await main.start_instrument()

        si_mocks["state"].reset.assert_not_called()
        si_mocks["heartbeat_tick"].assert_not_called()

    @pytest.mark.asyncio
    async def test_main_stays_running_after_startup(self, si_mocks):
        heartbeat_started = asyncio.Event()

        async def running_heartbeat(_istate):
            heartbeat_started.set()
            await asyncio.Future()

        si_mocks["heartbeat_tick"].side_effect = running_heartbeat

        task = asyncio.create_task(main.start_instrument())
        await asyncio.wait_for(heartbeat_started.wait(), timeout=1.0)

        assert not task.done()
        si_mocks["state"].reset.assert_called_once_with()
        si_mocks["heartbeat_tick"].assert_called_once_with(si_mocks["state"])

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


class TestMain:
    @pytest.fixture
    def main_mocks(self, monkeypatch):
        with (
            patch("main.mqtt.MQTTPublisher.get_instance") as mock_publisher,
            patch("main.asyncio.run") as mock_async_run,
            patch(
                "main.start_instrument", new_callable=MagicMock
            ) as mock_start_instrument,
            patch("main.traceback.print_exc") as mock_print_exc,
        ):
            monkeypatch.setenv("MQTT_HOST", "test-host")
            monkeypatch.setenv("MQTT_USER", "test-user")
            monkeypatch.setenv("MQTT_PASS", "test-pass")
            monkeypatch.setenv("INSTRUMENT_NAME", "test-instrument")
            mock_publisher.return_value = MagicMock()

            async def start_instrument_coroutine():
                return None

            mock_start_instrument.return_value = start_instrument_coroutine()
            yield {
                "publisher": mock_publisher,
                "publisher_instance": mock_publisher.return_value,
                "async_run": mock_async_run,
                "start_instrument": mock_start_instrument,
                "print_exc": mock_print_exc,
            }

    def test_initialises_publisher_and_runs_start_instrument(self, main_mocks):
        main.main()

        main_mocks["publisher"].assert_called_once_with(
            broker_address="test-host",
            user="test-user",
            password="test-pass",
            id="publisher_test-instrument",
        )
        main_mocks["start_instrument"].assert_called_once()
        main_mocks["async_run"].assert_called_once_with(
            main_mocks["start_instrument"].return_value
        )
        assert inspect.iscoroutine(main_mocks["start_instrument"].return_value)
        main_mocks["start_instrument"].return_value.close()
        main_mocks["publisher_instance"].assert_not_called()

    def test_publishes_unhandled_exception(self, main_mocks):
        error = RuntimeError("startup failed")
        main_mocks["async_run"].side_effect = error

        main.main()

        main_mocks["async_run"].assert_called_once()
        assert main_mocks["async_run"].call_args.args[0] is (
            main_mocks["start_instrument"].return_value
        )
        main_mocks["start_instrument"].return_value.close()
        main_mocks["print_exc"].assert_called_once_with()
        main_mocks["publisher"].assert_any_call(
            broker_address="test-host",
            user="test-user",
            password="test-pass",
            id="publisher_test-instrument",
        )
        main_mocks["publisher"].assert_any_call()
        main_mocks["publisher_instance"].publish.assert_called_once_with(
            "error/instrument",
            '{"code": "exception", "message": "[test-instrument] startup failed"}',
        )
