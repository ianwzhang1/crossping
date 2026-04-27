from __future__ import annotations

from dataclasses import replace
from typing import Callable, Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None

from .config import AppConfig, COLOR_OPTIONS

ACTIVATION_MODE_OPTIONS = (
    ("ctrl_shift", "Ctrl+Shift"),
    ("middle_click", "Middle Click"),
)

ACTIVATION_MODE_HELP = {
    "ctrl_shift": "Hold Ctrl+Shift to arm drawing. Left-drag draws. Right-click clears your strokes.",
    "middle_click": "Middle-click sends a ping ripple. Hold Shift and middle-drag to draw. Ctrl+middle-click clears your strokes.",
}


if QtWidgets is not None:
    class SettingsWindow(QtWidgets.QWidget):
        connect_requested = QtCore.Signal(AppConfig)
        disconnect_requested = QtCore.Signal()
        runtime_settings_changed = QtCore.Signal(AppConfig)
        clear_all_requested = QtCore.Signal()

        def __init__(self, config: AppConfig, is_connected: Callable[[], bool]) -> None:
            super().__init__()
            self._config = config
            self._is_connected = is_connected
            self.setWindowTitle("CrossPing")
            self.room_input = QtWidgets.QLineEdit(config.room_code)
            self.broker_input = QtWidgets.QLineEdit(config.broker_host)
            self.port_input = QtWidgets.QSpinBox()
            self.port_input.setRange(1, 65535)
            self.port_input.setValue(config.broker_port)
            self.activation_mode_input = QtWidgets.QComboBox()
            for value, label in ACTIVATION_MODE_OPTIONS:
                self.activation_mode_input.addItem(label, value)
            current_index = self.activation_mode_input.findData(config.activation_mode)
            self.activation_mode_input.setCurrentIndex(max(0, current_index))
            self.activation_mode_help = QtWidgets.QLabel()
            self.activation_mode_help.setWordWrap(True)
            self.activation_mode_input.currentIndexChanged.connect(self._update_activation_mode_help)
            self.activation_mode_input.currentIndexChanged.connect(self._emit_runtime_settings_change)
            self.color_input = QtWidgets.QComboBox()
            for value, label in COLOR_OPTIONS:
                self.color_input.addItem(label, value)
            current_color_index = self.color_input.findData(config.color)
            self.color_input.setCurrentIndex(max(0, current_color_index))
            self.color_input.currentIndexChanged.connect(self._emit_runtime_settings_change)
            self.color_help = QtWidgets.QLabel("Your selected color is used for both strokes and ping ripples.")
            self.color_help.setWordWrap(True)
            self.status_label = QtWidgets.QLabel("Disconnected")
            self.toggle_button = QtWidgets.QPushButton("Connect")
            self.toggle_button.clicked.connect(self._on_toggle)
            self.clear_all_button = QtWidgets.QPushButton("Clear All Drawings")
            self.clear_all_button.clicked.connect(self.clear_all_requested.emit)
            self.clear_all_help = QtWidgets.QLabel("Clears every visible drawing in the current room for everyone connected.")
            self.clear_all_help.setWordWrap(True)
            self.drawer_list = QtWidgets.QListWidget()
            self.drawer_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
            self.drawer_list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self.sent_feed = QtWidgets.QPlainTextEdit()
            self.sent_feed.setReadOnly(True)
            self.sent_feed.setMaximumBlockCount(200)
            self.received_feed = QtWidgets.QPlainTextEdit()
            self.received_feed.setReadOnly(True)
            self.received_feed.setMaximumBlockCount(200)

            form = QtWidgets.QFormLayout()
            form.addRow("Room", self.room_input)
            form.addRow("Broker", self.broker_input)
            form.addRow("Port", self.port_input)
            form.addRow("Controls", self.activation_mode_input)
            form.addRow("Color", self.color_input)

            layout = QtWidgets.QVBoxLayout(self)
            layout.addLayout(form)
            layout.addWidget(self.activation_mode_help)
            layout.addWidget(self.color_help)
            layout.addWidget(self.status_label)
            layout.addWidget(self.toggle_button)
            layout.addWidget(self.clear_all_button)
            layout.addWidget(self.clear_all_help)
            drawers_group = QtWidgets.QGroupBox("Visible Drawers")
            drawers_layout = QtWidgets.QVBoxLayout(drawers_group)
            drawers_layout.addWidget(self.drawer_list)
            layout.addWidget(drawers_group)
            feed_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
            sent_group = QtWidgets.QGroupBox("Sent Feed")
            sent_layout = QtWidgets.QVBoxLayout(sent_group)
            sent_layout.addWidget(self.sent_feed)
            received_group = QtWidgets.QGroupBox("Received Feed")
            received_layout = QtWidgets.QVBoxLayout(received_group)
            received_layout.addWidget(self.received_feed)
            feed_splitter.addWidget(sent_group)
            feed_splitter.addWidget(received_group)
            feed_splitter.setSizes([1, 1])
            layout.addWidget(feed_splitter, 1)
            self._update_activation_mode_help()
            self._refresh_status()
            self.set_visible_senders([], config.sender_id)

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:
            event.accept()
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()

        def show_and_focus(self) -> None:
            self.show()
            self.raise_()
            self.activateWindow()

        def set_connected(self, connected: bool, status_text: Optional[str] = None) -> None:
            self.status_label.setText(status_text or ("Connected" if connected else "Disconnected"))
            self.toggle_button.setText("Disconnect" if connected else "Connect")
            self.toggle_button.setEnabled(True)

        def set_config(self, config: AppConfig) -> None:
            self._config = config
            self.room_input.setText(config.room_code)
            self.broker_input.setText(config.broker_host)
            self.port_input.setValue(config.broker_port)
            index = self.activation_mode_input.findData(config.activation_mode)
            self.activation_mode_input.setCurrentIndex(max(0, index))
            color_index = self.color_input.findData(config.color)
            self.color_input.setCurrentIndex(max(0, color_index))
            self._update_activation_mode_help()

        def set_connecting(self) -> None:
            self.status_label.setText("Connecting...")
            self.toggle_button.setText("Connect")
            self.toggle_button.setEnabled(False)

        def _refresh_status(self) -> None:
            self.set_connected(self._is_connected())

        def _on_toggle(self) -> None:
            if self._is_connected():
                self.disconnect_requested.emit()
                return
            config = self._current_config()
            self._config = config
            self.connect_requested.emit(config)

        def _update_activation_mode_help(self) -> None:
            activation_mode = str(self.activation_mode_input.currentData())
            self.activation_mode_help.setText(ACTIVATION_MODE_HELP.get(activation_mode, ""))

        def _current_config(self) -> AppConfig:
            return replace(
                self._config,
                room_code=self.room_input.text(),
                broker_host=self.broker_input.text().strip(),
                broker_port=self.port_input.value(),
                activation_mode=str(self.activation_mode_input.currentData()),
                color=str(self.color_input.currentData()),
            )

        def _emit_runtime_settings_change(self) -> None:
            config = self._current_config()
            self._config = config
            self.runtime_settings_changed.emit(config)

        def append_sent_feed(self, line: str) -> None:
            self.sent_feed.appendPlainText(line)

        def append_received_feed(self, line: str) -> None:
            self.received_feed.appendPlainText(line)

        def set_visible_senders(self, sender_ids: list[str], local_sender_id: str) -> None:
            self.drawer_list.clear()
            if not sender_ids:
                item = QtWidgets.QListWidgetItem("No visible drawings yet.")
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.drawer_list.addItem(item)
                return
            for sender_id in sender_ids:
                label = f"{sender_id} (You)" if sender_id == local_sender_id else sender_id
                self.drawer_list.addItem(label)
else:
    class SettingsWindow:  # pragma: no cover
        def __init__(self, config: AppConfig, is_connected: Callable[[], bool]) -> None:
            self.config = config
            self.is_connected = is_connected

        def set_config(self, config: AppConfig) -> None:
            self.config = config

        def append_sent_feed(self, line: str) -> None:
            return None

        def append_received_feed(self, line: str) -> None:
            return None

        def set_visible_senders(self, sender_ids: list[str], local_sender_id: str) -> None:
            return None
