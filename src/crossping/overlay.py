from __future__ import annotations

import logging
import sys
import time
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None

try:
    import objc
    from AppKit import (
        NSApp,
        NSBackingStoreBuffered,
        NSBezierPath,
        NSColor,
        NSFont,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSPanel,
        NSScreen,
        NSScreenSaverWindowLevel,
        NSStatusWindowLevel,
        NSString,
        NSView,
        NSWindowCollectionBehaviorCanJoinAllApplications,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
        NSWindowStyleMaskBorderless,
        NSWorkspace,
        NSWorkspaceActiveSpaceDidChangeNotification,
    )
    from Foundation import NSMakeRect, NSObject
except ImportError:  # pragma: no cover
    objc = None
    NSApp = None
    NSBackingStoreBuffered = None
    NSBezierPath = None
    NSColor = None
    NSFont = None
    NSFontAttributeName = None
    NSForegroundColorAttributeName = None
    NSPanel = None
    NSScreen = None
    NSScreenSaverWindowLevel = None
    NSStatusWindowLevel = None
    NSString = None
    NSView = None
    NSWindowCollectionBehaviorCanJoinAllApplications = None
    NSWindowCollectionBehaviorCanJoinAllSpaces = None
    NSWindowCollectionBehaviorFullScreenAuxiliary = None
    NSWindowCollectionBehaviorStationary = None
    NSWindowStyleMaskBorderless = None
    NSWorkspace = None
    NSWorkspaceActiveSpaceDidChangeNotification = None
    NSMakeRect = None
    NSObject = None

from .logging_utils import LOGGER_NAME
from .protocol import denormalize_point
from .state import StrokeStore


def _hex_to_nscolor(value: str, alpha: float = 1.0) -> object:
    value = value.lstrip("#")
    if len(value) != 6 or NSColor is None:
        return NSColor.clearColor() if NSColor is not None else None
    red = int(value[0:2], 16) / 255.0
    green = int(value[2:4], 16) / 255.0
    blue = int(value[4:6], 16) / 255.0
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)


def _rect_components(rect: object) -> tuple[float, float, float, float]:
    if hasattr(rect, "origin") and hasattr(rect, "size"):
        return rect.origin.x, rect.origin.y, rect.size.width, rect.size.height
    return rect[0][0], rect[0][1], rect[1][0], rect[1][1]


def _union_screen_rect() -> tuple[float, float, float, float]:
    if NSScreen is None:
        return 0.0, 0.0, 1920.0, 1080.0
    screens = list(NSScreen.screens() or [])
    if not screens:
        return 0.0, 0.0, 1920.0, 1080.0
    rects = [_rect_components(screen.frame()) for screen in screens]
    min_x = min(rect[0] for rect in rects)
    min_y = min(rect[1] for rect in rects)
    max_x = max(rect[0] + rect[2] for rect in rects)
    max_y = max(rect[1] + rect[3] for rect in rects)
    return min_x, min_y, max_x - min_x, max_y - min_y


if QtWidgets is not None and sys.platform == "darwin" and objc is not None and NSView is not None and NSObject is not None:
    class _SpaceChangeObserver(NSObject):
        def initWithOverlay_(self, overlay: "OverlayWindow"):
            self = objc.super(_SpaceChangeObserver, self).init()
            if self is None:
                return None
            self.overlay = overlay
            return self

        def activeSpaceDidChange_(self, notification: object) -> None:
            self.overlay._handle_active_space_changed()


    class _OverlayContentView(NSView):
        def initWithOverlay_(self, overlay: "OverlayWindow"):
            self = objc.super(_OverlayContentView, self).init()
            if self is None:
                return None
            self.overlay = overlay
            return self

        def isOpaque(self) -> bool:
            return False

        def isFlipped(self) -> bool:
            return True

        def drawRect_(self, rect: object) -> None:
            overlay = self.overlay
            width = max(1.0, self.bounds().size.width)
            height = max(1.0, self.bounds().size.height)
            overlay.logger.debug("native paint event strokes=%s draw_mode=%s", len(overlay.store.all_strokes()), overlay.draw_mode_active)

            for stroke in overlay.store.all_strokes():
                if not stroke.points:
                    continue
                color = _hex_to_nscolor(stroke.color, 1.0)
                color.set()
                if len(stroke.points) == 1:
                    px, py = denormalize_point(stroke.points[0][0], stroke.points[0][1], width, height)
                    path = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(px - 2.0, py - 2.0, 4.0, 4.0))
                    path.fill()
                    continue
                path = NSBezierPath.bezierPath()
                path.setLineWidth_(stroke.width)
                first_x, first_y = denormalize_point(stroke.points[0][0], stroke.points[0][1], width, height)
                path.moveToPoint_((first_x, first_y))
                for point_x, point_y in stroke.points[1:]:
                    dx, dy = denormalize_point(point_x, point_y, width, height)
                    path.lineToPoint_((dx, dy))
                path.stroke()

            now = time.time()
            for ping in overlay._pings:
                age = max(0.0, now - float(ping["timestamp"]))
                progress = min(1.0, age / 0.9)
                radius = 18.0 + progress * 80.0
                alpha = max(0.0, 0.78 * (1.0 - progress))
                px, py = denormalize_point(float(ping["x"]), float(ping["y"]), width, height)
                ring_color = _hex_to_nscolor(str(ping.get("color", "#ff3366")), alpha)
                ring_color.set()
                ring = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(px - radius, py - radius, radius * 2.0, radius * 2.0))
                ring.setLineWidth_(max(1.0, 5.0 - (progress * 3.0)))
                ring.stroke()
                core_radius = 5.0
                core_color = _hex_to_nscolor(str(ping.get("color", "#ff3366")), max(0.0, 0.7 * (1.0 - progress)))
                core_color.set()
                core = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(px - core_radius, py - core_radius, core_radius * 2.0, core_radius * 2.0))
                core.fill()

            font = NSFont.fontWithName_size_("Menlo", 18.0) or NSFont.monospacedSystemFontOfSize_weight_(18.0, 0.0)
            for text_annotation in overlay.store.all_text_annotations():
                px, py = denormalize_point(text_annotation.x, text_annotation.y, width, height)
                color = _hex_to_nscolor(text_annotation.color, 1.0)
                attributes = {
                    NSFontAttributeName: font,
                    NSForegroundColorAttributeName: color,
                }
                lines = (text_annotation.text or "").split("\n")
                line_height = font.ascender() - font.descender() + font.leading()
                for index, line in enumerate(lines):
                    draw_text = line
                    if index == len(lines) - 1 and text_annotation.active:
                        draw_text = f"{draw_text}|"
                    NSString.stringWithString_(draw_text).drawAtPoint_withAttributes_((px, py + (index * line_height)), attributes)


    class OverlayWindow(QtCore.QObject):
        def __init__(self, store: StrokeStore) -> None:
            super().__init__()
            self.logger = logging.getLogger(LOGGER_NAME)
            self.store = store
            self.draw_mode_active = False
            self._pings = []
            self._tracked_screens = []
            self._space_observer = None
            self._space_notification_center = None
            self._window = None
            self._view = None
            self._build_native_window()
            self._install_screen_hooks()
            self._install_space_change_observer()
            self._animation_timer = QtCore.QTimer(self)
            self._animation_timer.setInterval(16)
            self._animation_timer.timeout.connect(self._tick_animation)

        def _build_native_window(self) -> None:
            x, y, width, height = _union_screen_rect()
            rect = NSMakeRect(x, y, width, height)
            self._window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            self._window.setOpaque_(False)
            self._window.setBackgroundColor_(NSColor.clearColor())
            self._window.setHasShadow_(False)
            self._window.setHidesOnDeactivate_(False)
            self._window.setFloatingPanel_(True)
            self._window.setBecomesKeyOnlyIfNeeded_(True)
            level = NSScreenSaverWindowLevel if NSScreenSaverWindowLevel is not None else NSStatusWindowLevel
            self._window.setLevel_(level)
            behavior = NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
            if NSWindowCollectionBehaviorCanJoinAllApplications is not None:
                behavior |= NSWindowCollectionBehaviorCanJoinAllApplications
            if NSWindowCollectionBehaviorFullScreenAuxiliary is not None:
                behavior |= NSWindowCollectionBehaviorFullScreenAuxiliary
            self._window.setCollectionBehavior_(behavior)
            self._window.setIgnoresMouseEvents_(True)
            self._view = _OverlayContentView.alloc().initWithOverlay_(self)
            self._view.setFrame_(rect)
            self._window.setContentView_(self._view)
            self._window.orderFront_(None)
            NSApp.activateIgnoringOtherApps_(False)
            self.logger.info(
                "native overlay initialized geometry=(%s,%s %sx%s) level=%s can_join_all_apps=%s",
                x,
                y,
                width,
                height,
                level,
                NSWindowCollectionBehaviorCanJoinAllApplications is not None,
            )

        def refresh(self) -> None:
            if self._view is not None:
                self._view.setNeedsDisplay_(True)

        def add_ping(self, sender_id: str, x: float, y: float, timestamp: float) -> None:
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": "#ff3366"})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.refresh()

        def add_colored_ping(self, sender_id: str, x: float, y: float, timestamp: float, color: str) -> None:
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": color})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.refresh()

        def set_draw_mode_active(self, active: bool, interactive: bool = True) -> None:
            self.draw_mode_active = active
            passthrough = (not active) or (not interactive)
            self.logger.info("native overlay draw mode active=%s interactive=%s passthrough=%s", active, interactive, passthrough)
            if self._window is not None:
                self._window.setIgnoresMouseEvents_(passthrough)
            self.refresh()

        def _tick_animation(self) -> None:
            now = time.time()
            self._pings = [ping for ping in self._pings if now - float(ping["timestamp"]) <= 0.9]
            if not self._pings:
                self._animation_timer.stop()
            self.refresh()

        def _install_screen_hooks(self) -> None:
            app = QtGui.QGuiApplication.instance()
            if app is None:
                return
            if hasattr(app, "screenAdded"):
                app.screenAdded.connect(lambda screen: self._reconnect_screen_hooks())
            if hasattr(app, "screenRemoved"):
                app.screenRemoved.connect(lambda screen: self._reconnect_screen_hooks())
            self._reconnect_screen_hooks()

        def _reconnect_screen_hooks(self) -> None:
            self._tracked_screens = list(QtGui.QGuiApplication.screens())
            for screen in self._tracked_screens:
                if hasattr(screen, "geometryChanged"):
                    screen.geometryChanged.connect(self._handle_screen_geometry_changed, QtCore.Qt.ConnectionType.UniqueConnection)
                if hasattr(screen, "virtualGeometryChanged"):
                    screen.virtualGeometryChanged.connect(self._handle_screen_geometry_changed, QtCore.Qt.ConnectionType.UniqueConnection)
            QtCore.QTimer.singleShot(0, self._refresh_geometry)

        def _handle_screen_geometry_changed(self, *args: object) -> None:
            QtCore.QTimer.singleShot(0, self._refresh_geometry)

        def _refresh_geometry(self) -> None:
            if self._window is None or self._view is None:
                return
            x, y, width, height = _union_screen_rect()
            rect = NSMakeRect(x, y, width, height)
            self._window.setFrame_display_(rect, True)
            self._view.setFrame_(NSMakeRect(0.0, 0.0, width, height))
            self._window.orderFront_(None)
            self.refresh()

        def _install_space_change_observer(self) -> None:
            if NSWorkspace is None:
                return
            workspace = NSWorkspace.sharedWorkspace()
            notification_center = workspace.notificationCenter()
            observer = _SpaceChangeObserver.alloc().initWithOverlay_(self)
            notification_center.addObserver_selector_name_object_(
                observer,
                b"activeSpaceDidChange:",
                NSWorkspaceActiveSpaceDidChangeNotification,
                None,
            )
            self._space_observer = observer
            self._space_notification_center = notification_center
            self.logger.info("installed native macOS active space observer")

        def _handle_active_space_changed(self) -> None:
            self.logger.info("native overlay active space changed")
            QtCore.QTimer.singleShot(0, self._refresh_geometry)

else:
    class OverlayWindow(QtWidgets.QWidget if QtWidgets is not None else object):  # pragma: no cover
        def __init__(self, store: StrokeStore) -> None:
            if QtWidgets is None:
                self.store = store
                return
            super().__init__()
            self.logger = logging.getLogger(LOGGER_NAME)
            self.store = store
            self.draw_mode_active = False
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
            self._animation_timer = QtCore.QTimer(self)
            self._animation_timer.setInterval(16)
            self._animation_timer.timeout.connect(self._tick_animation)

        def refresh(self) -> None:
            if QtWidgets is not None:
                self.update()

        def add_ping(self, sender_id: str, x: float, y: float, timestamp: float) -> None:
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": "#ff3366"})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.update()

        def add_colored_ping(self, sender_id: str, x: float, y: float, timestamp: float, color: str) -> None:
            self._pings.append({"sender_id": sender_id, "x": x, "y": y, "timestamp": time.time(), "color": color})
            if not self._animation_timer.isActive():
                self._animation_timer.start()
            self.update()

        def set_draw_mode_active(self, active: bool, interactive: bool = True) -> None:
            self.draw_mode_active = active
            passthrough = (not active) or (not interactive)
            self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, passthrough)
            self.show()
            self.update()

        def _tick_animation(self) -> None:
            now = time.time()
            self._pings = [ping for ping in self._pings if now - float(ping["timestamp"]) <= 0.9]
            if not self._pings:
                self._animation_timer.stop()
            self.update()

        def paintEvent(self, event: QtGui.QPaintEvent) -> None:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            width = max(1, self.width())
            height = max(1, self.height())
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
                for point_x, point_y in stroke.points[1:]:
                    dx, dy = denormalize_point(point_x, point_y, width, height)
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
