from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Optional

from .logging_utils import LOGGER_NAME
from .protocol import decode_message, topic_for_room

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None


class MQTTClient:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        room_code: str,
        on_message: Callable[[dict[str, object]], None],
        on_raw_message: Optional[Callable[[str], None]] = None,
        on_connection_state_change: Optional[Callable[[bool], None]] = None,
        client_factory: Optional[Callable[[], object]] = None,
    ) -> None:
        self.logger = logging.getLogger(LOGGER_NAME)
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.room_code = room_code
        self.topic = topic_for_room(room_code)
        self.on_message = on_message
        self.on_raw_message = on_raw_message
        self.on_connection_state_change = on_connection_state_change
        factory = client_factory
        if factory is None:
            if mqtt is None:  # pragma: no cover
                raise RuntimeError("paho-mqtt is required to use MQTTClient")
            factory = lambda: mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client = factory()
        self._connected = False

        if hasattr(self.client, "on_connect"):
            self.client.on_connect = self._handle_connect
        if hasattr(self.client, "on_message"):
            self.client.on_message = self._handle_message
        if hasattr(self.client, "on_disconnect"):
            self.client.on_disconnect = self._handle_disconnect

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self.logger.info("mqtt connect_async host=%s port=%s topic=%s", self.broker_host, self.broker_port, self.topic)
        self.client.connect_async(self.broker_host, self.broker_port, keepalive=30)
        self.client.loop_start()

    def disconnect(self, wait: bool = True) -> None:
        self.logger.info("mqtt disconnect")
        try:
            self.client.disconnect()
        except Exception:
            self.logger.exception("mqtt disconnect request failed")
        if wait:
            self.client.loop_stop()
        else:
            threading.Thread(target=self._loop_stop_background, name="crossping-mqtt-stop", daemon=True).start()
        self._connected = False

    def _loop_stop_background(self) -> None:
        try:
            self.client.loop_stop()
        except Exception:
            self.logger.exception("mqtt loop_stop failed")

    def publish(self, payload: str, wait: bool = False) -> None:
        self.logger.debug("mqtt publish topic=%s payload=%s", self.topic, payload)
        publish_result = self.client.publish(self.topic, payload)
        if wait and hasattr(publish_result, "wait_for_publish"):
            publish_result.wait_for_publish()

    def _handle_connect(self, client: object, userdata: object, flags: object, reason_code: object, properties: Optional[object] = None) -> None:
        self._connected = True
        self.logger.info("mqtt connected topic=%s", self.topic)
        client.subscribe(self.topic)
        if self.on_connection_state_change is not None:
            self.on_connection_state_change(True)

    def _handle_disconnect(self, client: object, userdata: object, flags: object, reason_code: object, properties: Optional[object] = None) -> None:
        self._connected = False
        self.logger.info("mqtt disconnected")
        if self.on_connection_state_change is not None:
            self.on_connection_state_change(False)

    def _handle_message(self, client: object, userdata: object, message: object) -> None:
        payload = getattr(message, "payload", b"")
        self.logger.debug("mqtt message payload=%s", payload)
        if isinstance(payload, bytes):
            decoded_payload = payload.decode("utf-8")
        else:
            decoded_payload = str(payload)
        if self.on_raw_message is not None:
            self.on_raw_message(decoded_payload)
        self.on_message(decode_message(decoded_payload))
