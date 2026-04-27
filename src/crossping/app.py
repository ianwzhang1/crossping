from __future__ import annotations

import json
import logging
import signal
import sys
import time
from typing import Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PySide6 is required to run CrossPing") from exc

from .config import AppConfig
from .input_hook import GlobalInputController
from .logging_utils import LOGGER_NAME, setup_logging
from .mqtt_client import MQTTClient
from .overlay import OverlayWindow
from .protocol import (
    ClearAllMessage,
    ClearSenderMessage,
    TextEndMessage,
    TextStartMessage,
    TextUpdateMessage,
)
from .state import StrokeStore
from .ui import SettingsWindow


class EventBridge(QtCore.QObject):
    message_received = QtCore.Signal(dict)
    connection_changed = QtCore.Signal(bool)
    draw_mode_changed = QtCore.Signal(bool)
    received_payload = QtCore.Signal(str)
    sent_payload = QtCore.Signal(str)
    local_clear_requested = QtCore.Signal()


class CrossPingApp:
    def __init__(self) -> None:
        log_path = setup_logging()
        self.logger = logging.getLogger(LOGGER_NAME)
        self.qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self._signal_timer = QtCore.QTimer()
        self._signal_timer.setInterval(250)
        self._signal_timer.timeout.connect(lambda: None)
        self.config = AppConfig.load()
        self.logger.info("app starting log_path=%s room=%s sender=%s", log_path, self.config.room_code, self.config.sender_id)
        self.store = StrokeStore()
        self.bridge = EventBridge()
        self.bridge.message_received.connect(self.handle_message)
        self.bridge.connection_changed.connect(self._handle_connection_changed)
        self.bridge.received_payload.connect(self._append_received_feed)
        self.bridge.sent_payload.connect(self._append_sent_feed)
        self.bridge.local_clear_requested.connect(self.clear_local_sender)
        self.overlay = OverlayWindow(self.store)
        self.bridge.draw_mode_changed.connect(self.overlay_draw_mode_changed)
        self.client = None  # type: Optional[MQTTClient]
        self.window = SettingsWindow(self.config, self.is_connected)
        self.window.connect_requested.connect(self.connect)
        self.window.disconnect_requested.connect(self.disconnect)
        self.window.runtime_settings_changed.connect(self.apply_runtime_settings)
        self.window.clear_all_requested.connect(self.clear_all_drawings_and_publish)
        self.window.show()
        self._refresh_drawer_list()
        self.tray_icon = self._create_tray_icon()
        self.qt_app.aboutToQuit.connect(self.shutdown)

        primary = QtGui.QGuiApplication.primaryScreen()
        def virtual_geometry() -> QtCore.QRect:
            screen = QtGui.QGuiApplication.primaryScreen()
            return screen.virtualGeometry() if screen is not None else QtCore.QRect(0, 0, 1920, 1080)

        self.input_controller = GlobalInputController(
            sender_id=self.config.sender_id,
            screen_size_provider=lambda: (
                virtual_geometry().width(),
                virtual_geometry().height(),
            ),
            pointer_position_provider=lambda: (
                QtGui.QCursor.pos().x() - virtual_geometry().x(),
                QtGui.QCursor.pos().y() - virtual_geometry().y(),
            ),
            input_enabled_provider=self.is_connected,
            publish=self.publish,
            on_local_clear=self.request_local_clear,
            on_draw_mode_changed=self._emit_draw_mode_changed,
            color_provider=lambda: self.config.color,
            activation_mode=self.config.activation_mode,
        )
        self.input_controller.set_color(self.config.color)
        if primary is not None:
            geometry = virtual_geometry()
            self.logger.info(
                "virtual desktop geometry=(%s,%s %sx%s) primary_geometry=(%s,%s %sx%s) dpr=%.3f",
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
                primary.geometry().x(),
                primary.geometry().y(),
                primary.geometry().width(),
                primary.geometry().height(),
                primary.devicePixelRatio(),
            )

    def run(self) -> int:
        self.logger.info("run starting")
        self._install_signal_handlers()
        self.input_controller.start()
        self.connect(self.config)
        self._signal_timer.start()
        return self.qt_app.exec()

    def _install_signal_handlers(self) -> None:
        def handle_sigint(signum: int, frame: object) -> None:
            self.logger.info("received signal signum=%s, quitting application", signum)
            self.qt_app.quit()

        try:
            signal.signal(signal.SIGINT, handle_sigint)
        except ValueError:
            self.logger.debug("unable to install SIGINT handler outside main thread")
        else:
            self.logger.info("installed SIGINT handler for terminal Ctrl+C")

    def is_connected(self) -> bool:
        return self.client is not None and self.client.is_connected

    def connect(self, config: AppConfig) -> None:
        if self.client is not None:
            self.disconnect()
        self.apply_runtime_settings(config)
        self.logger.info("connecting broker=%s port=%s room=%s", config.broker_host, config.broker_port, config.room_code)
        self.window.set_connecting()
        self.client = MQTTClient(
            broker_host=config.broker_host,
            broker_port=config.broker_port,
            room_code=config.room_code,
            on_message=self._handle_remote_message,
            on_raw_message=self._handle_raw_incoming_payload,
            on_connection_state_change=self._emit_connection_change,
        )
        self.client.connect()

    def disconnect(self) -> None:
        self.logger.info("disconnect requested")
        if self.client is not None:
            self.client.disconnect(wait=False)
            self.client = None
        self.input_controller.refresh_enabled_state()
        self.window.set_connected(False)

    def apply_runtime_settings(self, config: AppConfig) -> None:
        self.config = config
        self.config.save()
        self.input_controller.set_activation_mode(config.activation_mode)
        self.input_controller.set_color(config.color)
        self.window.set_config(config)
        self.logger.info("applied runtime settings activation_mode=%s color=%s", config.activation_mode, config.color)

    def publish(self, payload: str) -> None:
        self.logger.debug("publish payload=%s", payload)
        self.bridge.sent_payload.emit(payload)
        self.handle_message_from_payload(payload)
        if self.client is not None:
            self.client.publish(payload)

    def clear_local_sender(self) -> None:
        self.logger.info("clear local sender=%s", self.config.sender_id)
        self.store.clear_sender(self.config.sender_id)
        self._refresh_drawer_list()
        self.overlay.refresh()

    def request_local_clear(self) -> None:
        self.bridge.local_clear_requested.emit()

    def clear_local_sender_and_publish(self) -> None:
        self.clear_local_sender()
        self.publish(ClearSenderMessage.build(self.config.sender_id).encode())

    def clear_all_drawings(self) -> None:
        self.logger.info("clear all drawings sender=%s", self.config.sender_id)
        self.store.clear_all()
        self._refresh_drawer_list()
        self.overlay.refresh()

    def clear_all_drawings_and_publish(self) -> None:
        self.clear_all_drawings()
        self.publish(ClearAllMessage.build(self.config.sender_id).encode())

    def handle_message_from_payload(self, payload: str) -> None:
        from .protocol import decode_message

        self.logger.debug("decode local payload=%s", payload)
        self.bridge.message_received.emit(decode_message(payload))

    def _handle_remote_message(self, message: dict[str, object]) -> None:
        if str(message.get("sender_id", "")) == self.config.sender_id:
            self.logger.debug("ignoring self echo message=%s", message)
            return
        self.logger.info("received remote message=%s", message)
        self.bridge.message_received.emit(message)

    def _handle_raw_incoming_payload(self, payload: str) -> None:
        self.bridge.received_payload.emit(payload)

    def _emit_connection_change(self, connected: bool) -> None:
        self.bridge.connection_changed.emit(connected)

    def _handle_connection_changed(self, connected: bool) -> None:
        if connected and self.client is None:
            return
        self.logger.info("connection changed connected=%s", connected)
        self.input_controller.refresh_enabled_state()
        self.window.set_connected(connected)

    def _emit_draw_mode_changed(self, active: bool) -> None:
        self.logger.info("draw mode changed active=%s", active)
        self.bridge.draw_mode_changed.emit(active)

    def overlay_draw_mode_changed(self, active: bool) -> None:
        self.logger.debug("overlay draw mode active=%s", active)
        self.overlay.set_draw_mode_active(active, interactive=self.config.activation_mode == "ctrl_shift")

    def handle_message(self, message: dict[str, object]) -> None:
        sender_id = str(message.get("sender_id", ""))
        message_type = message.get("type")
        self.logger.debug("handle message type=%s sender=%s", message_type, sender_id)
        if message_type == "stroke_start":
            self.store.start_stroke(
                sender_id=sender_id,
                stroke_id=str(message.get("stroke_id", "")),
                color=str(message.get("color", "#ff3366")),
                width=float(message.get("width", 3.0)),
            )
        elif message_type == "stroke_point":
            self.store.add_point(
                sender_id=sender_id,
                stroke_id=str(message.get("stroke_id", "")),
                x=float(message.get("x", 0.0)),
                y=float(message.get("y", 0.0)),
                color=str(message.get("color", "#ff3366")),
            )
        elif message_type == "stroke_end":
            self.store.end_stroke(sender_id=sender_id, stroke_id=str(message.get("stroke_id", "")))
        elif message_type == "clear_sender":
            self.store.clear_sender(sender_id=sender_id)
        elif message_type == "clear_all":
            self.store.clear_all()
        elif message_type == "ping":
            self.overlay.add_colored_ping(
                sender_id=sender_id,
                x=float(message.get("x", 0.0)),
                y=float(message.get("y", 0.0)),
                timestamp=float(message.get("timestamp", 0.0)),
                color=str(message.get("color", "#ff3366")),
            )
        elif message_type == "text_start":
            self.store.start_text(
                sender_id=sender_id,
                text_id=str(message.get("text_id", "")),
                x=float(message.get("x", 0.0)),
                y=float(message.get("y", 0.0)),
                color=str(message.get("color", "#ff3366")),
            )
        elif message_type == "text_update":
            self.store.update_text(
                sender_id=sender_id,
                text_id=str(message.get("text_id", "")),
                text=str(message.get("text", "")),
                color=str(message.get("color", "#ff3366")),
            )
        elif message_type == "text_end":
            self.store.end_text(sender_id=sender_id, text_id=str(message.get("text_id", "")))
        self.logger.debug("stroke count=%s", len(self.store.all_strokes()))
        self._refresh_drawer_list()
        self.overlay.refresh()

    def shutdown(self) -> None:
        self.logger.info("shutdown")
        self.input_controller.stop()
        self._clear_remote_sender_on_shutdown()
        self.disconnect()
        if self.tray_icon is not None:
            self.tray_icon.hide()

    def _clear_remote_sender_on_shutdown(self) -> None:
        if not self.is_connected() or self.client is None:
            return
        self.logger.info("publishing shutdown clear for sender=%s", self.config.sender_id)
        self.clear_local_sender()
        payload = ClearSenderMessage.build(self.config.sender_id).encode()
        self.bridge.sent_payload.emit(payload)
        self.handle_message_from_payload(payload)
        self.client.publish(payload, wait=True)

    def show_settings(self) -> None:
        self.window.show_and_focus()

    def _create_tray_icon(self) -> Optional[QtWidgets.QSystemTrayIcon]:
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return None
        tray_icon = QtWidgets.QSystemTrayIcon(self.qt_app.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon))
        menu = QtWidgets.QMenu()
        show_action = menu.addAction("Show CrossPing")
        quit_action = menu.addAction("Quit")
        show_action.triggered.connect(self.show_settings)
        quit_action.triggered.connect(self.qt_app.quit)
        tray_icon.setContextMenu(menu)
        tray_icon.activated.connect(lambda reason: self.show_settings() if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger else None)
        tray_icon.show()
        return tray_icon

    def _format_feed_line(self, direction: str, payload: str) -> str:
        timestamp = time.strftime("%H:%M:%S")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            rendered = payload
        else:
            rendered = json.dumps(parsed, separators=(",", ":"), sort_keys=True)
        return f"[{timestamp}] {direction} {rendered}"

    def _append_received_feed(self, payload: str) -> None:
        self.window.append_received_feed(self._format_feed_line("recv", payload))

    def _append_sent_feed(self, payload: str) -> None:
        self.window.append_sent_feed(self._format_feed_line("send", payload))

    def _refresh_drawer_list(self) -> None:
        self.window.set_visible_senders(self.store.sender_ids(), self.config.sender_id)
