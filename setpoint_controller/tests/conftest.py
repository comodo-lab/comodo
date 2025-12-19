"""Shared pytest fixtures and utilities for setpoint controller tests."""

import json
import pytest
from unittest.mock import patch, MagicMock
from random import uniform as rand

import threading
import fnmatch
from typing import Dict

from setpoint_controller import SetpointController
from src.pid import PID


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to access test results and execute code on test failure.
    This allows fixtures to know if their test failed.
    """
    outcome = yield
    rep = outcome.get_result()

    # Store the test result in the item for fixtures to access
    setattr(item, f"rep_{rep.when}", rep)


class MockMessage:
    """
    Mock MQTT message object.
    """

    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else payload


def parse_message_args(args):
    """
    Parses the arguments received by an mqtt client (i.e. [topic, payload]),
    and returns the topic and loaded JSON message (a dict).
    Example usage:
        topic, message = parse_message_args(mock_mqtt_publisher.publish.call_args[0])
    """
    topic, payload = args
    return topic, json.loads(payload)


@pytest.fixture(autouse=True)
def mock_MQTTClient(message_bus):
    """Mock the MQTTClient singleton."""
    with patch("setpoint_controller.MQTTClient") as mock_client_class:
        mock_instance = MagicMock()

        def create_client(*args, **kwargs):
            # Extract init parameters
            client_id = kwargs.get("id", "client")
            callback = kwargs.get("callback")
            topics = kwargs.get("topics", [])
            obj = kwargs.get("obj")
            # Set properties on the mock instance
            mock_instance.id = client_id
            mock_instance.obj = obj
            mock_instance.callback = callback

            # Wrapper to adapt message bus callback to MQTT client callback signature
            def callback_wrapper(topic, msg):
                if callback is not None:
                    # Pass mock_instance as `client`
                    callback(mock_instance, msg, obj)

            # Subscribe to topics using the message bus
            if isinstance(topics, str):
                topics = [topics]
            for topic in topics:
                message_bus.subscribe(topic, callback_wrapper)

        mock_client_class.side_effect = create_client
        mock_client_class.return_value = mock_instance

        yield mock_client_class


@pytest.fixture(autouse=True)
def mock_load_message():
    """Mock the load_message function to handle MockMessage objects."""
    # Patch where it's actually imported and used
    with patch("setpoint_controller.load_message") as mock:

        def load_message(msg):
            payload = msg.payload if hasattr(msg, "payload") else msg
            if isinstance(payload, bytes):
                return json.loads(payload.decode("utf-8"))
            elif isinstance(payload, str):
                return json.loads(payload)

        mock.side_effect = load_message
        yield mock


@pytest.fixture(autouse=True)
def mock_MQTTPublisher(message_bus):
    """Mock the MQTTPublisher singleton."""
    with patch("setpoint_controller.MQTTPublisher") as mock_publisher_class:
        mock_instance = MagicMock()
        mock_instance.publish.side_effect = message_bus.publish
        mock_publisher_class.get_instance.return_value = mock_instance
        yield mock_instance


class InMemoryMessageBus:
    """
    A thread-safe in-memory message bus that simulates MQTT publish/subscribe behaviour.
    The message history can be accessed through the get_messages method, optionally filtered by topic.
    """

    def __init__(self):
        self.subscribers: Dict[str, list] = {}  # pattern -> list of callbacks
        self.lock = threading.Lock()
        self.message_history: list[MockMessage] = []

    def subscribe(self, topic_pattern: str, callback: callable):
        """Subscribe a callback to a topic pattern (supports * wildcards)."""
        with self.lock:
            if topic_pattern not in self.subscribers:
                self.subscribers[topic_pattern] = []
            self.subscribers[topic_pattern].append(callback)

    def publish(self, topic: str, payload):
        """Publish a message to a topic."""
        if isinstance(payload, str):
            msg = MockMessage(topic=topic, payload=payload.encode("utf-8"))
        else:
            msg = payload

        with self.lock:
            self.message_history.append(msg)

            # Notify all subscribers whose patterns match this topic
            for pattern, callbacks in self.subscribers.items():
                if fnmatch.fnmatch(topic, pattern):
                    for callback in callbacks:
                        # Call callback in a separate thread to simulate async behaviour
                        threading.Thread(
                            target=callback, args=(topic, msg), daemon=True
                        ).start()

    def get_messages(self, topic: str = None) -> list[MockMessage]:
        """Get message history, optionally filtered by topic."""
        with self.lock:
            if not topic:
                return self.message_history.copy()
            if any(c in topic for c in "*?[]"):  # accept wildcard characters
                return [
                    m for m in self.message_history if fnmatch.fnmatch(m.topic, topic)
                ]
            return [m for m in self.message_history if m.topic == topic]


@pytest.fixture
def message_bus(request):
    """Provide a fresh message bus for each test."""
    message_bus = InMemoryMessageBus()
    yield message_bus

    # After test completes, if the test failed, print message bus history
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        print("Message Bus History:")
        print("-" * 60)
        messages = message_bus.get_messages()
        first_n = 50 if len(messages) > 50 else len(messages)
        lasst_n = 50 if len(messages) > 100 else max(0, len(messages) - first_n)
        for i, message in enumerate(messages[:first_n]):
            print(f" [{i}] {message.topic}: {message.payload.decode('utf-8')}")
        if lasst_n > 0:
            print("...  " * 10 + "\n")
        for i, message in enumerate(messages[-lasst_n:]):
            print(f" [{i}] {message.topic}: {message.payload.decode('utf-8')}")
        print("-" * 60 + "\n")


def base_SPC(**kwargs):
    """
    Create a SetpointController with default values for mqtt and sensor/actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        SetpointController instance
    """
    d_kwargs = {
        "mqtt_host": "test_host",
        "mqtt_user": "test_user",
        "mqtt_pass": "test_pass",
        "sensor": "test_sensor",
        "actuator": "test_actuator",
        "sensor": "A",
        "actuator": "B",
        "heartbeat_interval": 1,
    }
    d_kwargs.update(kwargs)

    # Create and return SetpointController instance
    return SetpointController(**d_kwargs)


def base_PID(**kwargs):
    """
    Create a PID controller with default values for id, sensor and actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        PID instance
    """
    d_kwargs = {"id": "test_pid", "sensor": "mock_sensor", "actuator": "mock_actuator"}

    d_kwargs.update(kwargs)

    # Create and return PID instance
    return PID(**d_kwargs)


@pytest.fixture
def mock_spc():
    """SetpointController with default parameters."""
    spc = MagicMock(spec=SetpointController)
    spc.state = {
        "name": f"pid_A__B",
        "status": "no_setpoint",
        "setpoint": None,
        "config": {"mock": "config"},
    }
    spc.pid = base_PID()
    return spc


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    return base_PID()


@pytest.fixture
def rand_pid():
    """PID with random parameters."""
    return base_PID(
        k_p=rand(0.01, 10.0),
        k_i=rand(0.01, 10.0),
        k_d=rand(0.01, 10.0),
        k_aw=rand(0.01, 10.0),
        k_df=rand(0.01, 10.0),
        max=rand(0.01, 10.0),
        min=rand(0.01, 10.0),
        max_rate=rand(0.01, 10.0),
    )


@pytest.fixture
def mock_pid_time():
    """Mock time.time() only within PID.step for deterministic testing."""
    mock_time = [0.0]

    def increment_time():
        result = mock_time[0]
        mock_time[0] += 1  # 1 second per call
        return result

    with patch("src.pid.PID.now", side_effect=increment_time):
        yield mock_time
