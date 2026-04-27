import threading
from types import SimpleNamespace

from crossping.mqtt_client import MQTTClient


class FakeMQTTClient:
    def __init__(self) -> None:
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.connected = []
        self.subscriptions = []
        self.published = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.waited_for_publish = False

    def connect_async(self, host: str, port: int, keepalive: int = 30) -> None:
        self.connected.append((host, port, keepalive))

    def loop_start(self) -> None:
        self.loop_started = True

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnected = True

    def subscribe(self, topic: str) -> None:
        self.subscriptions.append(topic)

    def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))
        return self

    def wait_for_publish(self) -> None:
        self.waited_for_publish = True


def test_mqtt_client_connects_publishes_and_decodes_messages() -> None:
    fake = FakeMQTTClient()
    received = []
    raw_received = []
    connection_changes = []
    client = MQTTClient(
        broker_host="broker.example",
        broker_port=1883,
        room_code="Room 7",
        on_message=received.append,
        on_raw_message=raw_received.append,
        on_connection_state_change=connection_changes.append,
        client_factory=lambda: fake,
    )

    client.connect()
    assert fake.connected == [("broker.example", 1883, 30)]
    assert fake.loop_started is True

    client._handle_connect(fake, None, None, 0)
    assert client.is_connected is True
    assert fake.subscriptions == ["crossping/room7"]
    assert connection_changes == [True]

    client.publish('{"type":"clear_sender","sender_id":"abc","timestamp":1}')
    assert fake.published == [("crossping/room7", '{"type":"clear_sender","sender_id":"abc","timestamp":1}')]

    client.publish('{"type":"clear_sender","sender_id":"abc","timestamp":2}', wait=True)
    assert fake.waited_for_publish is True

    fake_message = SimpleNamespace(payload=b'{"type":"clear_sender","sender_id":"abc","timestamp":1}')
    client._handle_message(fake, None, fake_message)
    assert raw_received == ['{"type":"clear_sender","sender_id":"abc","timestamp":1}']
    assert received == [{"type": "clear_sender", "sender_id": "abc", "timestamp": 1}]

    client.disconnect()
    assert fake.disconnected is True
    assert fake.loop_stopped is True


def test_mqtt_client_can_disconnect_without_waiting() -> None:
    fake = FakeMQTTClient()
    started = threading.Event()
    released = threading.Event()

    def blocking_loop_stop() -> None:
        started.set()
        released.wait(timeout=2)
        fake.loop_stopped = True

    fake.loop_stop = blocking_loop_stop
    client = MQTTClient(
        broker_host="broker.example",
        broker_port=1883,
        room_code="Room 7",
        on_message=lambda payload: None,
        client_factory=lambda: fake,
    )

    client.disconnect(wait=False)
    assert fake.disconnected is True
    assert started.wait(timeout=1) is True
    released.set()
