"""Mock implementations for MQTT clients for testing."""

import pytest

import json
import threading
from unittest.mock import patch, MagicMock
from paho.mqtt.client import topic_matches_sub


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
        self.subscribers: dict[str, list] = {}  # pattern -> list of callbacks
        self.lock = threading.Lock()
        self.message_history: list[MockMessage] = []

    def subscribe(self, topic_pattern: str, callback: callable):
        """
        Subscribe a callback to a topic pattern.
        Supports single level and multi-level wildcards (e.g., "a/+/c" or "a/#").
        """
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
                if topic_matches_sub(pattern, topic):
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
            elif any(c in topic for c in "*?[]#+"):  # accept wildcard characters
                history = [
                    m for m in self.message_history if topic_matches_sub(topic, m.topic)
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

    Exposes mocks for:
        - client_class
        - client_instance
        - publisher_class
        - publisher_instance
    """
    with (
        patch("utils.mqtt_clients.MQTTClient") as mock_client_class,
        patch("utils.mqtt_clients.MQTTPublisher") as mock_publisher_class,
    ):
        # -----------------------
        # Mock MQTTClient
        # -----------------------
        created_clients = {}

        def create_client(*args, **kwargs):
            # Extract init parameters
            client_id = kwargs.get("id", "client")
            callback = kwargs.get("callback")
            topics = kwargs.get("topics", [])
            obj = kwargs.get("obj")

            # Reuse existing client if already created
            if client_id in created_clients:
                client = created_clients[client_id]
                client.callback = callback
                client.obj = obj
                return client

            # Create new mock instance
            mock_client_instance = MagicMock()
            mock_client_instance.id = client_id
            mock_client_instance.obj = obj
            mock_client_instance.callback = callback
            mock_client_instance.publish.side_effect = message_bus.publish

            # Wrapper to adapt message bus callback to MQTT client callback signature
            # Accesses the current callback dynamically (so it reacts to callback changes)
            def callback_wrapper(topic, msg):
                if mock_client_instance.callback is not None:
                    mock_client_instance.callback(
                        mock_client_instance,
                        msg,
                        mock_client_instance.obj,
                    )

            # Subscribe to topics using the message bus
            if isinstance(topics, str):
                topics = [topics]
            for topic in topics:
                message_bus.subscribe(topic, callback_wrapper)

            created_clients[client_id] = mock_client_instance
            return mock_client_instance

        mock_client_class.side_effect = create_client

        class ClientProxy:
            """Proxy that returns a specific client by ID or the most recently created client."""

            # When called with a client_id, returns that client
            def __call__(self, client_id=None):
                if not created_clients:
                    raise AttributeError("No MQTT clients have been created yet")

                if client_id is not None:
                    if client_id not in created_clients:
                        raise AttributeError(f"No client with id '{client_id}' found")
                    return created_clients[client_id]

            # When not called with a client_id, returns the most recently created client
            def __getattr__(self, name):
                if created_clients != {}:
                    client = next(reversed(created_clients.values()))
                else:
                    raise AttributeError("No MQTT clients have been created yet")
                return getattr(client, name)

        # -----------------------
        # Mock MQTTPublisher
        # -----------------------
        mock_publisher_instance = MagicMock()
        mock_publisher_instance.publish.side_effect = message_bus.publish
        mock_publisher_instance.client.publish.side_effect = message_bus.publish
        mock_publisher_class.get_instance.return_value = mock_publisher_instance
        mock_publisher_class._instance = mock_publisher_instance

        # -----------------------
        # Expose mocks to tests
        # -----------------------
        yield {
            "client_class": mock_client_class,
            "client_instance": ClientProxy(),
            "publisher_class": mock_publisher_class,
            "publisher_instance": mock_publisher_instance,
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
