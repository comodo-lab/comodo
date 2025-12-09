"""Mock implementations for MQTT clients for testing."""

import pytest

import json
import threading
import fnmatch
from typing import Dict
from unittest.mock import patch, MagicMock


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to access test results and execute code on test failure.
    This allows fixtures to know if their test failed.
    It is used byt the message_bus fixture, to print the message history on failure.
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

    def get_messages(self, topic: str = None, decoded=False) -> list[MockMessage]:
        """Get message history, optionally filtered by topic."""
        with self.lock:
            if not topic:
                history = self.message_history.copy()
            elif any(c in topic for c in "*?[]"):  # accept wildcard characters
                history = [
                    m for m in self.message_history if fnmatch.fnmatch(m.topic, topic)
                ]
            else:
                history = [m for m in self.message_history if m.topic == topic]
            if decoded:
                for m in history:
                    if isinstance(m.payload, bytes):
                        m.payload = m.payload.decode("utf-8")
            return history


@pytest.fixture
def message_bus(request):
    """
    Provides a fresh message bus for each test.

    Any test that covers code that is expected to interact with the MQTT broker
    should use this fixture to get a clean message bus instance.
    The MQTT clients and publisher need also be mocked (autouse is set to True).
    After the test completes, if it failed, the message bus history
    is printed to the console for debugging.
    """
    message_bus = InMemoryMessageBus()
    yield message_bus

    # After test completes, if the test failed, print message bus history
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        print_n = 30
        half_n = int(print_n / 2)
        print("Message Bus History:")
        print("-" * 60)
        messages = message_bus.get_messages(decoded=True)
        total = len(messages)
        first_n = half_n if total > half_n else total
        last_n = half_n if total > print_n else max(0, total - first_n)
        for i, message in enumerate(messages[:first_n]):
            print(f" [{i}] {message.topic}: {message.payload}")
        if total > print_n:
            print("...  " * 10 + "\n")
        if last_n > 0:
            for i, message in enumerate(messages[-last_n:]):
                print(f" [{total-last_n+i}] {message.topic}: {message.payload}")
        print("-" * 60 + "\n")


@pytest.fixture(autouse=True)
def mqtt_mocks(message_bus):
    """
    Unified autouse fixture that patches:
      - utils.mqtt_clients.MQTTClient
      - utils.mqtt_clients.MQTTPublisher
      - utils.mqtt_clients.load_message

    Exposes mocks for:
      - client_class
      - client_instance
      - publisher_class
      - publisher_instance
      - load_message
    """
    with (
        patch("utils.mqtt_clients.MQTTClient") as mock_client_class,
        patch("utils.mqtt_clients.MQTTPublisher") as mock_publisher_class,
        patch("utils.mqtt_clients.load_message") as mock_load,
    ):
        # -----------------------
        # Mock MQTTClient
        # -----------------------
        mock_client_instance = MagicMock()

        def create_client(*args, **kwargs):
            # Extract init parameters
            client_id = kwargs.get("id", "client")
            callback = kwargs.get("callback")
            topics = kwargs.get("topics", [])
            obj = kwargs.get("obj")
            # Set properties on the mock instance
            mock_client_instance.id = client_id
            mock_client_instance.obj = obj
            mock_client_instance.callback = callback

            # Wrapper to adapt message bus callback to MQTT client callback signature
            def callback_wrapper(topic, msg):
                if callback is not None:
                    callback(mock_client_instance, msg, obj)

            # Subscribe to topics using the message bus
            if isinstance(topics, str):
                topics = [topics]
            for topic in topics:
                message_bus.subscribe(topic, callback_wrapper)

        mock_client_class.side_effect = create_client
        mock_client_class.return_value = mock_client_instance

        # -----------------------
        # Mock MQTTPublisher
        # -----------------------
        mock_publisher_instance = MagicMock()
        mock_publisher_instance.publish.side_effect = message_bus.publish
        mock_publisher_class.get_instance.return_value = mock_publisher_instance
        mock_publisher_class._instance = mock_publisher_instance

        # -----------------------
        # Mock load_message
        # -----------------------
        def load_message(msg):
            payload = msg.payload if hasattr(msg, "payload") else msg
            if isinstance(payload, bytes):
                return json.loads(payload.decode("utf-8"))
            elif isinstance(payload, str):
                return json.loads(payload)

        mock_load.side_effect = load_message

        # -----------------------
        # Expose mocks to tests
        # -----------------------
        yield {
            "client_class": mock_client_class,
            "client_instance": mock_client_instance,
            "publisher_class": mock_publisher_class,
            "publisher_instance": mock_publisher_instance,
            "load_message": mock_load,
        }


def parse_message_args(args):
    """
    Parses the arguments received by an mqtt client (i.e. [topic, payload]),
    and returns the topic and loaded JSON message (a dict).
    Example usage:
        topic, message = parse_message_args(publisher.publish.call_args[0])
    """
    topic, payload = args
    return topic, json.loads(payload)
