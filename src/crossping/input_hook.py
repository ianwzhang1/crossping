from __future__ import annotations

import logging
import secrets
import sys
from collections.abc import Callable
from typing import Optional, Tuple

try:
    from pynput import keyboard, mouse
except ImportError:  # pragma: no cover
    keyboard = mouse = None

try:
    import Quartz
except ImportError:  # pragma: no cover
    Quartz = None

from .config import DEFAULT_ACTIVATION_MODE
from .logging_utils import LOGGER_NAME
from .protocol import ClearSenderMessage, PingMessage, StrokeEndMessage, StrokePointMessage, StrokeStartMessage, normalize_point

WM_MOUSEMOVE = 0x0200
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209


class GlobalInputController:
    def __init__(
        self,
        sender_id: str,
        screen_size_provider: Callable[[], Tuple[int, int]],
        publish: Callable[[str], None],
        on_local_clear: Callable[[], None],
        on_draw_mode_changed: Callable[[bool], None],
        color_provider: Callable[[], str],
        activation_mode: str = DEFAULT_ACTIVATION_MODE,
    ) -> None:
        self.sender_id = sender_id
        self.screen_size_provider = screen_size_provider
        self.publish = publish
        self.on_local_clear = on_local_clear
        self.on_draw_mode_changed = on_draw_mode_changed
        self.color_provider = color_provider
        self.logger = logging.getLogger(LOGGER_NAME)
        self.activation_mode = activation_mode
        self.ctrl_down = False
        self.shift_down = False
        self.keyboard_listener = None
        self.mouse_listener = None
        self._draw_mode_active = False
        self.active_stroke_id = None  # type: Optional[str]

    def set_activation_mode(self, activation_mode: str) -> None:
        self.logger.info("activation mode set to %s", activation_mode)
        self.activation_mode = activation_mode
        self._end_stroke_if_needed("activation mode change")
        self._sync_draw_mode()

    def start(self) -> None:
        if keyboard is None or mouse is None:  # pragma: no cover
            raise RuntimeError("pynput is required to use GlobalInputController")
        self.logger.info("starting global input controller")
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        mouse_listener_kwargs = {
            "on_click": self._on_click,
            "on_move": self._on_move,
        }
        if sys.platform == "darwin" and Quartz is not None:
            mouse_listener_kwargs["darwin_intercept"] = self._darwin_mouse_intercept
        if sys.platform.startswith("win"):
            mouse_listener_kwargs["win32_event_filter"] = self._win32_mouse_filter
        self.mouse_listener = mouse.Listener(**mouse_listener_kwargs)
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self) -> None:
        if self.keyboard_listener is not None:
            self.logger.info("stopping global input controller")
            self.keyboard_listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()

    def _should_intercept(self) -> bool:
        if self.activation_mode == "middle_click":
            return self.shift_down
        return self.ctrl_down and self.shift_down

    def _sync_draw_mode(self) -> None:
        active = self._should_intercept()
        if active == self._draw_mode_active:
            return
        self._draw_mode_active = active
        self.logger.info(
            "global draw mode active=%s ctrl=%s shift=%s activation_mode=%s",
            active,
            self.ctrl_down,
            self.shift_down,
            self.activation_mode,
        )
        self.on_draw_mode_changed(active)

    def _on_key_press(self, key: object) -> None:
        if keyboard is None:  # pragma: no cover
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_down = True
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            self.shift_down = True
        self._sync_draw_mode()

    def _on_key_release(self, key: object) -> None:
        if keyboard is None:  # pragma: no cover
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_down = False
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            self.shift_down = False
        self._sync_draw_mode()
        if not self._draw_mode_active:
            self._end_stroke_if_needed("modifier release")

    def _on_click(self, x: int, y: int, button: object, pressed: bool) -> None:
        if mouse is None:
            return
        if button != mouse.Button.middle and self.activation_mode == "middle_click":
            return
        if self.activation_mode == "middle_click":
            self._handle_middle_click_mode(x, y, button, pressed)
            return
        self._handle_ctrl_shift_mode(x, y, button, pressed)

    def _handle_ctrl_shift_mode(self, x: int, y: int, button: object, pressed: bool) -> None:
        if mouse is None or not self._draw_mode_active:
            return
        if button == mouse.Button.left and pressed:
            self.active_stroke_id = secrets.token_hex(8)
            self.logger.info("global mouse press stroke_id=%s x=%s y=%s", self.active_stroke_id, x, y)
            self.publish(StrokeStartMessage.build(self.sender_id, self.active_stroke_id).encode())
            self._publish_point(x, y)
            return
        if button == mouse.Button.left and not pressed and self.active_stroke_id is not None:
            self.logger.info("global mouse release stroke_id=%s", self.active_stroke_id)
            self.publish(StrokeEndMessage.build(self.sender_id, self.active_stroke_id).encode())
            self.active_stroke_id = None
            return
        if button == mouse.Button.right and pressed:
            self.logger.info("global right click clear x=%s y=%s", x, y)
            self.on_local_clear()
            self.publish(ClearSenderMessage.build(self.sender_id).encode())

    def _handle_middle_click_mode(self, x: int, y: int, button: object, pressed: bool) -> None:
        if mouse is None or button != mouse.Button.middle:
            return
        if self.ctrl_down and pressed:
            self.logger.info("middle click clear x=%s y=%s", x, y)
            self.on_local_clear()
            self.publish(ClearSenderMessage.build(self.sender_id).encode())
            return
        if self.shift_down and pressed:
            self.active_stroke_id = secrets.token_hex(8)
            self.logger.info("middle draw press stroke_id=%s x=%s y=%s", self.active_stroke_id, x, y)
            self.publish(StrokeStartMessage.build(self.sender_id, self.active_stroke_id).encode())
            self._publish_point(x, y)
            return
        if self.shift_down and not pressed and self.active_stroke_id is not None:
            self.logger.info("middle draw release stroke_id=%s", self.active_stroke_id)
            self.publish(StrokeEndMessage.build(self.sender_id, self.active_stroke_id).encode())
            self.active_stroke_id = None
            return
        if pressed:
            width, height = self.screen_size_provider()
            nx, ny = normalize_point(x, y, width, height)
            self.logger.info("middle click ping x=%.4f y=%.4f", nx, ny)
            self.publish(PingMessage.build(self.sender_id, nx, ny, color=self.color_provider()).encode())

    def _on_move(self, x: int, y: int) -> None:
        if self.active_stroke_id is None:
            return
        if self.activation_mode == "middle_click" and not self.shift_down:
            return
        if self.activation_mode == "ctrl_shift" and not self._draw_mode_active:
            return
        self._publish_point(x, y)

    def _publish_point(self, x: int, y: int) -> None:
        width, height = self.screen_size_provider()
        nx, ny = normalize_point(x, y, width, height)
        self.logger.debug("global mouse point stroke_id=%s x=%.4f y=%.4f", self.active_stroke_id, nx, ny)
        self.publish(StrokePointMessage.build(self.sender_id, self.active_stroke_id or "", nx, ny).encode())

    def _end_stroke_if_needed(self, reason: str) -> None:
        if self.active_stroke_id is None:
            return
        self.logger.info("ending stroke from %s stroke_id=%s", reason, self.active_stroke_id)
        self.publish(StrokeEndMessage.build(self.sender_id, self.active_stroke_id).encode())
        self.active_stroke_id = None

    def _darwin_mouse_intercept(self, event_type: int, event: object) -> object:
        if Quartz is None or self.activation_mode != "middle_click":
            return event
        middle_button_number = 2
        middle_event_types = {
            Quartz.kCGEventOtherMouseDown,
            Quartz.kCGEventOtherMouseUp,
            Quartz.kCGEventOtherMouseDragged,
        }
        if event_type not in middle_event_types:
            return event
        button_number = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber)
        if button_number != middle_button_number:
            return event
        self.logger.debug("suppressing middle mouse event_type=%s", event_type)
        return None

    def _win32_mouse_filter(self, msg: int, data: object) -> Optional[bool]:
        if not self._should_suppress_windows_message(msg):
            return None
        if self.mouse_listener is not None:
            self.logger.debug("suppressing win32 mouse msg=%s", hex(msg))
            self.mouse_listener.suppress_event()
        return False

    def _should_suppress_windows_message(self, msg: int) -> bool:
        if self.activation_mode != "middle_click":
            return False
        if msg in (WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MBUTTONDBLCLK):
            return True
        if msg == WM_MOUSEMOVE and self.active_stroke_id is not None:
            return True
        return False
