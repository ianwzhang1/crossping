from __future__ import annotations

import logging
import os
import sys
from ctypes import c_void_p
from collections.abc import Callable
import time

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None

try:
    import objc
    from AppKit import (
        NSColor,
        NSStatusWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
    )
except ImportError:  # pragma: no cover
    objc = None
    NSColor = None
    NSStatusWindowLevel = None
    NSWindowCollectionBehaviorCanJoinAllSpaces = None
    NSWindowCollectionBehaviorFullScreenAuxiliary = None
    NSWindowCollectionBehaviorStationary = None

from .protocol import denormalize_point
from .state import StrokeStore
from .logging_utils import LOGGER_NAME


if QtWidgets is not None:
    class OverlayWindow(QtWidgets.QWidget):
        def __init__(
            self,
            store: StrokeStore,
            on_stroke_start: Callable[[str, float, float], None],
            on_stroke_point: Callable[[str, float, float], None],
            on_stroke_end: Callable[[str], None],
            on_clear: Callable[[], None],
        ) -> None:
            super().__init__()
            self.logger = logging.getLogger(LOGGER_NAME)
            self.store = store
            self.on_stroke_start = on_stroke_start
            self.on_stroke_point = on_stroke_point
            self.on_stroke_end = on_stroke_end
            self.on_clear = on_clear
            self.draw_mode_active = False
            self.active_stroke_id = None
            self._native_window = None
            self._pings = []
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setMouseTracking(True)
            self.setWindowFlags(
                QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.WindowStaysOnTopHint
                | QtCore.Qt.WindowType.Window
                | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
            )
            screen = QtGui.QGuiApplication.primaryScreen()
            geometry = screen.virtualGeometry() if screen is not None else QtCore.QRect(0, 0, 1920, 1080)
            self.setGeometry(geometry)
            self.show()
            self._apply_native_window_configuration()
            self._bring_to_front()
            self._animation_timer = QtCore.QTimer(self)
            self._animation_timer.setInterval(16)
            self._animation_timer.timeout.connect(self._tick_animation)
            self.logger.info(
                "overlay initialized geometry=(%s,%s %sx%s) native_window=%s",
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
                bool(self._native_window),
            )

        def refresh(self) -> None:
            self.logger.debug("overlay refresh requested")
            self.update()

        def add_ping(self, sender_id: str, x: float, y: float, timestamp: float) -> None:
            self.logger.info("overlay ping sender=%s x=%.4f y=%.4f", sender_id, x, y)
            # Animate from local receipt time so peer clock skew does not delay or skip pings.
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": "#ff3366"})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.update()

        def add_colored_ping(self, sender_id: str, x: float, y: float, timestamp: float, color: str) -> None:
            self.logger.info("overlay ping sender=%s x=%.4f y=%.4f color=%s", sender_id, x, y, color)
            # Animate from local receipt time so peer clock skew does not delay or skip pings.
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": color})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.update()

        def set_draw_mode_active(self, active: bool, interactive: bool = True) -> None:
            if not active and self.active_stroke_id is not None:
                self.on_stroke_end(self.active_stroke_id)
                self.active_stroke_id = None
                self.releaseMouse()
            self.draw_mode_active = active
            passthrough = (not active) or (not interactive)
            self.logger.info(
                "overlay draw mode active=%s interactive=%s passthrough=%s",
                active,
                interactive,
                passthrough,
            )
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, passthrough)
            self._set_native_mouse_passthrough(passthrough)
            self.show()
            self._bring_to_front()
            self.update()

        def _apply_native_window_configuration(self) -> None:
            if sys.platform != "darwin" or objc is None:
                return
            if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
                return
            try:
                native_object = objc.objc_object(c_void_p=int(self.winId()))
            except Exception:
                self._native_window = None
                return
            if native_object is None:
                return
            native_window = getattr(native_object, "window", None)
            if callable(native_window):
                native_object = native_window()
            self._native_window = native_object
            if self._native_window is None:
                return
            self._native_window.setOpaque_(False)
            self._native_window.setBackgroundColor_(NSColor.clearColor())
            self._native_window.setHasShadow_(False)
            self._native_window.setLevel_(NSStatusWindowLevel)
            behavior = (
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | NSWindowCollectionBehaviorStationary
            )
            self._native_window.setCollectionBehavior_(behavior)
            self._native_window.setIgnoresMouseEvents_(True)
            self._native_window.orderFrontRegardless()
            self.logger.info("applied native macOS window configuration")

        def _set_native_mouse_passthrough(self, passthrough: bool) -> None:
            if self._native_window is None:
                return
            self.logger.debug("native mouse passthrough=%s", passthrough)
            self._native_window.setIgnoresMouseEvents_(passthrough)

        def _bring_to_front(self) -> None:
            if self._native_window is not None:
                self._native_window.orderFrontRegardless()
            else:
                self.raise_()

        def _tick_animation(self) -> None:
            now = time.time()
            self._pings = [ping for ping in self._pings if now - float(ping["timestamp"]) <= 0.9]
            if not self._pings:
                self._animation_timer.stop()
                return
            self.update()

        def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
            if not self.draw_mode_active:
                self.logger.debug("ignored mouse press while draw mode inactive")
                event.ignore()
                return
            self.logger.debug("overlay intercepted mouse press button=%s", event.button())
            event.accept()

        def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
            if not self.draw_mode_active:
                event.ignore()
                return
            event.accept()

        def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
            event.accept()

        def paintEvent(self, event: QtGui.QPaintEvent) -> None:
            self.logger.debug("paint event strokes=%s draw_mode=%s", len(self.store.all_strokes()), self.draw_mode_active)
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            width = max(1, self.width())
            height = max(1, self.height())
            self.logger.debug(
                "paint geometry widget=(%s,%s %sx%s)",
                self.geometry().x(),
                self.geometry().y(),
                width,
                height,
            )
            if self.draw_mode_active:
                painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 1))
            for stroke in self.store.all_strokes():
                if not stroke.points:
                    continue
                pen = QtGui.QPen(QtGui.QColor(stroke.color))
                pen.setWidthF(stroke.width)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                if len(stroke.points) == 1:
                    px, py = denormalize_point(stroke.points[0][0], stroke.points[0][1], width, height)
                    painter.drawPoint(QtCore.QPointF(px, py))
                    continue
                path = QtGui.QPainterPath()
                first_x, first_y = denormalize_point(stroke.points[0][0], stroke.points[0][1], width, height)
                path.moveTo(first_x, first_y)
                for px, py in stroke.points[1:]:
                    dx, dy = denormalize_point(px, py, width, height)
                    path.lineTo(dx, dy)
                painter.drawPath(path)
            now = time.time()
            for ping in self._pings:
                age = max(0.0, now - float(ping["timestamp"]))
                progress = min(1.0, age / 0.9)
                radius = 18.0 + progress * 80.0
                alpha = max(0, int(200 * (1.0 - progress)))
                px, py = denormalize_point(float(ping["x"]), float(ping["y"]), width, height)
                base_color = QtGui.QColor(str(ping.get("color", "#ff3366")))
                ring_color = QtGui.QColor(base_color)
                ring_color.setAlpha(alpha)
                ping_pen = QtGui.QPen(ring_color)
                ping_pen.setWidthF(max(1.0, 5.0 - (progress * 3.0)))
                painter.setPen(ping_pen)
                painter.drawEllipse(QtCore.QPointF(px, py), radius, radius)
                core_color = QtGui.QColor(base_color)
                core_color.setAlpha(max(0, int(180 * (1.0 - progress))))
                core_brush = QtGui.QBrush(core_color)
                painter.setBrush(core_brush)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.drawEllipse(QtCore.QPointF(px, py), 5.0, 5.0)
            text_font = QtGui.QFont("Menlo" if sys.platform == "darwin" else "Consolas")
            text_font.setPointSizeF(18.0)
            painter.setFont(text_font)
            metrics = QtGui.QFontMetricsF(text_font)
            for text_annotation in self.store.all_text_annotations():
                px, py = denormalize_point(text_annotation.x, text_annotation.y, width, height)
                painter.setPen(QtGui.QPen(QtGui.QColor(text_annotation.color)))
                lines = (text_annotation.text or "").split("\n")
                for index, line in enumerate(lines):
                    draw_text = line
                    if index == len(lines) - 1 and text_annotation.active:
                        draw_text = f"{draw_text}|"
                    painter.drawText(QtCore.QPointF(px, py + (index * metrics.lineSpacing())), draw_text)
else:
    class OverlayWindow:  # pragma: no cover
        def __init__(
            self,
            store: StrokeStore,
            on_stroke_start: Callable[[str, float, float], None],
            on_stroke_point: Callable[[str, float, float], None],
            on_stroke_end: Callable[[str], None],
            on_clear: Callable[[], None],
        ) -> None:
            self.store = store

        def show(self) -> None:
            return None

        def refresh(self) -> None:
            return None

        def set_draw_mode_active(self, active: bool, interactive: bool = True) -> None:
            return None
