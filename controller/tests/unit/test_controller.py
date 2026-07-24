import pytest
from unittest.mock import patch, call

import json

from tests.conftest import (
    mock_state,
    message_bus,
    mqtt_mocks,
)

from controller import main


class TestMain:
    @pytest.fixture
    def main_mocks(self, mock_state, mqtt_mocks):
        with patch("os.environ") as mock_environ, patch(
            "os.getenv"
        ) as mock_getenv, patch(
            "controller.get_env_or_secret"
        ) as mock_get_secret, patch(
            "controller.comodo_config.ComodoConfig"
        ) as mock_comodo_config, patch(
            "controller.cstate"
        ) as mock_cstate, patch(
            "controller.t.sleep"
        ) as mock_sleep, patch(
            "controller.on_watchdog_message"
        ) as mock_on_watchdog_message, patch(
            "controller.on_wd_timer_message"
        ) as mock_on_wd_timer_message, patch(
            "controller.on_ui_message"
        ) as mock_on_ui_message, patch(
            "controller.c_idle"
        ) as mock_c_idle, patch(
            "controller.on_timer_message"
        ) as mock_on_timer_message, patch(
            "controller.on_heartbeat_message"
        ) as mock_on_heartbeat_message:
            env_values = {}
            mock_environ.keys.return_value = env_values.keys()
            mock_getenv.side_effect = lambda var, default=None: env_values.get(
                var, default
            )
            mock_get_secret.side_effect = (
                lambda var, file_var=None, default=None: env_values.get(var, default)
            )
            mock_loaded_config = mock_comodo_config.return_value.load.return_value
            mock_loaded_config.globals = {
                "watchdog_interval": 1,
                "watchdog_timeout": 5,
            }
            mock_cstate.return_value = mock_state("idle")

            yield {
                "env_values": env_values,
                "getenv": mock_getenv,
                "get_secret": mock_get_secret,
                "comodo_config_class": mock_comodo_config,
                "loaded_config": mock_loaded_config,
                "cstate": mock_cstate,
                "sleep": mock_sleep,
                "callbacks": {
                    "on_watchdog_message": mock_on_watchdog_message,
                    "on_wd_timer_message": mock_on_wd_timer_message,
                    "on_ui_message": mock_on_ui_message,
                    "c_idle": mock_c_idle,
                    "on_timer_message": mock_on_timer_message,
                    "on_heartbeat_message": mock_on_heartbeat_message,
                },
            }

    def test_env_vars_checked(self, main_mocks, capsys, message_bus):
        mocks = main_mocks
        mocks["getenv"].side_effect = SystemExit  # Exit early

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        expected_env_vars = [
            ["MQTT_HOST"],
            ["MQTT_USER"],
            ["MQTT_PASS", "MQTT_PASS_FILE"],
            ["MQTT_CONNECTION_TIMEOUT"],
            ["INFLUX_BUCKET"],
            ["INFLUX_HOST"],
            ["INFLUX_ORG"],
            ["INFLUX_TOKEN", "INFLUX_TOKEN_FILE"],
        ]
        for var_group in expected_env_vars:
            assert (
                f"WARNING: environment variables not set for: {', '.join(var_group)}."
                in captured.out
            )

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0

    def test_env_vars_loaded(self, main_mocks, message_bus):
        mocks = main_mocks
        mocks["cstate"].side_effect = SystemExit  # Exit early

        with pytest.raises(SystemExit):
            main()

        assert mocks["getenv"].call_args_list == [
            call("MQTT_HOST", "rabbitmq"),
            call("MQTT_USER", None),
            call("MQTT_CONNECTION_TIMEOUT", 10),
        ]
        mocks["get_secret"].assert_called_with("MQTT_PASS", "MQTT_PASS_FILE", None)

        mocks["cstate"].assert_called_once_with()

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0

    def test_creates_clients(self, main_mocks, mqtt_mocks, message_bus):
        mocks = main_mocks
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "MQTT_CONNECTION_TIMEOUT": 15,
            }
        )
        mocks["loaded_config"].globals = {
            "watchdog_interval": 2,
            "watchdog_timeout": 6,
        }
        wdog = {"interval": 2, "timeout": 6, "timer": 6, "healthy": False}
        state = mocks["cstate"].return_value
        mocks["sleep"].side_effect = SystemExit  # Exit early

        with pytest.raises(SystemExit):
            main()

        mqtt_mocks["publisher_class"].get_instance.assert_called_once_with(
            id="publisher_controller",
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            connection_timeout=15,
        )
        assert mqtt_mocks["client_class"].call_args_list == [
            call(
                id="watchdog",
                callback=mocks["callbacks"]["on_watchdog_message"],
                topics=[
                    "watchdog/timer/event/+",
                    "watchdog/timer/command/+",
                    "controller/heartbeat",
                    "error/exception",
                ],
                obj=wdog,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
            call(
                id="wd_timer",
                callback=mocks["callbacks"]["on_wd_timer_message"],
                topics="watchdog/timer/command/start",
                obj=wdog,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
            call(
                id="ui",
                callback=mocks["callbacks"]["on_ui_message"],
                topics="ui/#",
                obj=state,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
            call(
                id="controller",
                callback=mocks["callbacks"]["c_idle"],
                topics="controller/#",
                obj=state,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
            call(
                id="timer",
                callback=mocks["callbacks"]["on_timer_message"],
                topics="controller/timer/#",
                obj=state,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
            call(
                id="heartbeat",
                callback=mocks["callbacks"]["on_heartbeat_message"],
                topics="instruments/+/heartbeat",
                obj=state,
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                connection_timeout=15,
            ),
        ]

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/command/start"
        assert json.loads(messages[0].payload) == {"timeout": 6, "interval": 2}

    def test_watchdog_loop_not_started_if_unhealthy(
        self, main_mocks, message_bus, capsys
    ):
        mocks = main_mocks
        mocks["sleep"].side_effect = [1, 2, 3, SystemExit]  # Just in case loop starts

        main()

        mocks["sleep"].assert_called_once_with(1)  # Only initial sleep before wd starts
        messages = message_bus.get_messages(decoded=True)
        assert messages[0].topic == "watchdog/timer/command/start"
        assert json.loads(messages[0].payload) == {"timeout": 5, "interval": 1}
        captured = capsys.readouterr()
        assert "Creating clients..." in captured.out
        assert "Controller failed to start. watchdog unhealthy." in captured.out
        assert "Exiting..." in captured.out

    def test_watchdog_loop(self, main_mocks, mqtt_mocks, message_bus, capsys):
        mocks = main_mocks
        mocks["loaded_config"].globals = {
            "heartbeat_interval": 2,
            "watchdog_interval": 1,
            "watchdog_timeout": 6,
        }

        def wd_timer_side_effect(client, msg, obj):
            obj["healthy"] = True

        mocks["callbacks"]["on_wd_timer_message"].side_effect = wd_timer_side_effect
        mocks["sleep"].side_effect = [1, 2, 3, SystemExit]

        with pytest.raises(SystemExit):
            main()

        assert mocks["sleep"].call_args_list == [
            call(1),  # Before wd starts
            call(2),  # First loop
            call(2),  # Second loop
            call(2),  # Third loop
            # SystemExit called here
        ]
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 4
        assert messages[0].topic == "watchdog/timer/command/start"
        assert json.loads(messages[0].payload) == {"timeout": 6, "interval": 1}
        assert messages[1].topic == "controller/heartbeat"
        assert messages[2].topic == "controller/heartbeat"
        assert messages[3].topic == "controller/heartbeat"
        captured = capsys.readouterr()
        assert "Creating clients..." in captured.out
        assert "Controller started successfully." in captured.out
        assert "Exiting..." not in captured.out

    def test_watchdog_loop_exits_on_unhealthy(
        self, main_mocks, mqtt_mocks, message_bus, capsys
    ):
        mocks = main_mocks
        mocks["loaded_config"].globals = {
            "heartbeat_interval": 2,
            "watchdog_interval": 1,
            "watchdog_timeout": 6,
        }

        def wd_timer_side_effect(client, msg, obj):
            obj["healthy"] = True

        def wd_side_effect(client, msg, obj):
            if mocks["callbacks"]["on_watchdog_message"].call_count >= 4:
                obj["healthy"] = False

        mocks["callbacks"]["on_wd_timer_message"].side_effect = wd_timer_side_effect
        mocks["callbacks"]["on_watchdog_message"].side_effect = wd_side_effect
        mocks["sleep"].side_effect = [1, 2, 3, 4, 5, 6, 7, 8, 9, SystemExit]

        main()

        assert mocks["sleep"].call_args_list == [
            call(1),  # Before wd starts
            call(2),  # First loop
            call(2),  # Second loop
            call(2),  # Third loop
            # Should exit loop here
        ]
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) >= 4  # >= Setting healthy to false takes some time
        assert len(messages) <= 6  # <= But it shouldn't take that much time
        assert messages[0].topic == "watchdog/timer/command/start"
        assert messages[1].topic == "controller/heartbeat"
        assert messages[2].topic == "controller/heartbeat"
        assert messages[3].topic == "controller/heartbeat"
        captured = capsys.readouterr()
        assert "Creating clients..." in captured.out
        assert "Controller started successfully." in captured.out
        assert "Exiting..." in captured.out
