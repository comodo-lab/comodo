from unittest.mock import patch
import json

import pytest

from tests.conftest import MockMessage, mock_state, mock_instrument, firmware_env

from utils.mqtt_validator import MQTTValidationException
import src.watchdog as watchdog


class TestFirmwareWatchdog:
    @pytest.fixture
    def wd_mocks(self, mock_state, mqtt_mocks):
        with patch("src.watchdog.mqtt_val") as mock_mqtt_val:
            mock_mqtt_val.validate_message.side_effect = (
                lambda topic, payload: json.loads(payload)
            )
            mock_mqtt_val.MQTTValidationException = MQTTValidationException
            mock_state.status = "awaiting_experiment"
            yield {
                "state": mock_state,
                "client_class": mqtt_mocks["client_class"],
                "mqtt_val": mock_mqtt_val,
            }

    def create_watchdog(self, mocks, last_contact=10.0):
        """
        Creates the watchdog, armed by a heartbeat at time `last_contact` (None if never heard from).
        """
        wd = watchdog.FirmwareWatchdog(mocks["state"])
        wd.last_contact = last_contact
        return wd

    def heartbeat_msg(self, experiment_id=None):
        return MockMessage(
            topic="controller/heartbeat",
            payload=json.dumps(
                {
                    "config": {"experiment_id": experiment_id},
                    "setpoints": {},
                    "state": {"status": "idle"},
                }
            ),
        )

    def reset_msg(self):
        return MockMessage(topic="controller/command/reset", payload=json.dumps({}))

    # ========================================

    def test_init(self, wd_mocks):
        wd = watchdog.FirmwareWatchdog(wd_mocks["state"])

        config = wd_mocks["state"].instrument.config
        wd_mocks["client_class"].assert_called_once_with(
            id="test_instrument_watchdog",
            callback=wd.on_message,
            topics=["controller/heartbeat", "controller/command/reset"],
            broker_address=config["MQTT_HOST"],
            user=config["MQTT_USER"],
            password=config["MQTT_PASS"],
            connection_timeout=60,
        )
        assert wd.interval == 1.0
        # MAX_MISSED_HEARTBEATS x HEARTBEAT_INTERVAL
        assert wd.timeout == 3.0
        # Not armed until the controller is first heard from
        assert wd.last_contact is None

    def test_checks_every_interval_until_stopped(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        with (
            patch.object(wd._stopped, "wait", side_effect=[False, False, True]) as wait,
            patch.object(wd, "check") as check,
        ):
            wd.run()

        assert check.call_count == 2
        wait.assert_called_with(1.0)

    def test_start_and_stop(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        wd.interval = 0.01
        with patch.object(wd, "check") as check:
            wd.start()
            wd.stop()
            wd._thread.join(timeout=1)

            assert not wd._thread.is_alive()
            assert check.call_count <= 1

    def test_check_within_timeout(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        with patch("src.watchdog.time.monotonic", return_value=13.0):
            wd.check()

        wd_mocks["state"].safe_stop.assert_not_called()

    def test_check_safe_stops_after_timeout(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        with patch("src.watchdog.time.monotonic", return_value=13.5):
            wd.check()

        wd_mocks["state"].safe_stop.assert_called_once_with(
            "No valid heartbeats from the controller for more than 3.0s."
        )

    def test_check_does_not_safe_stop_before_armed(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks, last_contact=None)
        with patch("src.watchdog.time.monotonic", return_value=1000.0):
            wd.check()

        wd_mocks["state"].safe_stop.assert_not_called()

    def test_check_does_not_safe_stop_again(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["state"].status = "safe_stop"
        with patch("src.watchdog.time.monotonic", return_value=20.0):
            wd.check()

        wd_mocks["state"].safe_stop.assert_not_called()

    def test_on_message_routes_heartbeat_and_reset(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        with (
            patch.object(wd, "on_heartbeat") as on_heartbeat,
            patch.object(wd, "on_reset") as on_reset,
        ):
            wd.on_message(None, self.heartbeat_msg("e-123"))
            wd.on_message(None, self.reset_msg())

        on_heartbeat.assert_called_once_with(
            {
                "config": {"experiment_id": "e-123"},
                "setpoints": {},
                "state": {"status": "idle"},
            }
        )
        on_reset.assert_called_once_with()

    def test_on_message_ignores_invalid_message(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["mqtt_val"].validate_message.side_effect = MQTTValidationException(
            "invalid"
        )
        with (
            patch.object(wd, "on_heartbeat") as on_heartbeat,
            patch.object(wd, "on_reset") as on_reset,
        ):
            wd.on_message(None, self.heartbeat_msg())

        on_heartbeat.assert_not_called()
        on_reset.assert_not_called()
        captured = capsys.readouterr()
        assert (
            "WARNING: Ignoring invalid message on controller/heartbeat: invalid"
            in captured.out
        )

    def test_first_heartbeat_arms_the_watchdog(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks, last_contact=None)
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": None}})

        assert wd.last_contact == 12.0
        captured = capsys.readouterr()
        assert "test_instrument watchdog armed." in captured.out

    def test_later_heartbeats_do_not_print(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks)
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": None}})

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_first_heartbeat_arms_the_watchdog_even_for_another_experiment(
        self, wd_mocks, capsys
    ):
        wd = self.create_watchdog(wd_mocks, last_contact=None)
        wd_mocks["state"].instrument.config["experiment"]["experiment_id"] = "e-123"
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": None}})

        assert wd.last_contact == 12.0
        captured = capsys.readouterr()
        assert "test_instrument watchdog armed." in captured.out

    def test_heartbeat_refreshes_contact_without_experiment(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": "any-experiment"}})

        assert wd.last_contact == 12.0

    def test_heartbeat_for_the_experiment_refreshes_contact(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["state"].instrument.config["experiment"]["experiment_id"] = "e-123"
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": "e-123"}})

        assert wd.last_contact == 12.0

    def test_heartbeat_for_another_experiment_does_not_refresh_contact(self, wd_mocks):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["state"].instrument.config["experiment"]["experiment_id"] = "e-123"
        with patch("src.watchdog.time.monotonic", return_value=12.0):
            wd.on_heartbeat({"config": {"experiment_id": None}})

        assert wd.last_contact == 10.0

    def test_reset_clears_safe_stop_and_disarms(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["state"].status = "safe_stop"

        wd.on_reset()

        wd_mocks["state"].reset.assert_called_once_with()
        assert wd.last_contact is None
        captured = capsys.readouterr()
        assert "Safe stop cleared by a reset." in captured.out

    def test_reset_ends_running_experiment(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks)
        wd_mocks["state"].status = "running"
        wd_mocks["state"].instrument.config["experiment"]["experiment_id"] = "e-123"

        wd.on_reset()

        wd_mocks["state"].reset.assert_called_once_with()
        assert wd.last_contact is None
        captured = capsys.readouterr()
        assert "WARNING: Experiment e-123 ended by a reset." in captured.out

    def test_reset_while_awaiting_experiment(self, wd_mocks, capsys):
        wd = self.create_watchdog(wd_mocks)

        wd.on_reset()

        wd_mocks["state"].reset.assert_called_once_with()
        captured = capsys.readouterr()
        assert captured.out == ""
