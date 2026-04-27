from types import SimpleNamespace

from crossping.input_hook import GlobalInputController, mouse


def test_draw_mode_callback_tracks_modifier_state_changes() -> None:
    changes = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
        pointer_position_provider=lambda: (0, 0),
        input_enabled_provider=lambda: True,
        publish=lambda payload: None,
        on_local_clear=lambda: None,
        on_draw_mode_changed=changes.append,
        color_provider=lambda: "#ff3366",
        activation_mode="ctrl_shift",
    )

    controller.ctrl_down = True
    controller.shift_down = True
    controller._sync_draw_mode()
    controller._sync_draw_mode()
    controller.shift_down = False
    controller._sync_draw_mode()

    assert changes == [True, False]


def test_ctrl_shift_click_publishes_ping() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 20),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="ctrl_shift",
    )

    controller.ctrl_down = True
    controller.shift_down = True
    controller._sync_draw_mode()
    controller._handle_ctrl_shift_mode(10, 20, mouse.Button.left, True)
    controller._handle_ctrl_shift_mode(10, 20, mouse.Button.left, False)

    assert len(published) == 1
    assert '"type":"ping"' in published[0]


def test_ctrl_shift_drag_publishes_stroke_messages() -> None:
    published = []
    pointer = {"x": 10, "y": 20}
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (pointer["x"], pointer["y"]),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="ctrl_shift",
    )

    controller.ctrl_down = True
    controller.shift_down = True
    controller._sync_draw_mode()
    controller._handle_ctrl_shift_mode(10, 20, mouse.Button.left, True)
    pointer["x"] = 15
    pointer["y"] = 25
    controller._on_move(15, 25)
    controller._handle_ctrl_shift_mode(15, 25, mouse.Button.left, False)

    assert len(published) == 4
    assert '"type":"stroke_start"' in published[0]
    assert '"type":"stroke_point"' in published[1]
    assert '"type":"stroke_point"' in published[2]
    assert '"type":"stroke_end"' in published[3]


def test_middle_click_mode_ignores_modifier_state_changes() -> None:
    changes = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
        pointer_position_provider=lambda: (0, 0),
        input_enabled_provider=lambda: True,
        publish=lambda payload: None,
        on_local_clear=lambda: None,
        on_draw_mode_changed=changes.append,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    controller.ctrl_down = True
    controller._sync_draw_mode()
    controller.shift_down = True
    controller._sync_draw_mode()
    controller.shift_down = False
    controller._sync_draw_mode()

    assert changes == []


def test_windows_middle_click_suppression_rules() -> None:
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
        pointer_position_provider=lambda: (0, 0),
        input_enabled_provider=lambda: True,
        publish=lambda payload: None,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    assert controller._should_suppress_windows_message(0x0207) is True
    assert controller._should_suppress_windows_message(0x0208) is True
    assert controller._should_suppress_windows_message(0x0209) is True
    assert controller._should_suppress_windows_message(0x0200) is False


def test_middle_click_drag_publishes_stroke_messages() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 10),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    controller._handle_middle_click_mode(10, 10, mouse.Button.middle, True)
    controller.pointer_position_provider = lambda: (15, 20)
    controller._on_move(15, 20)
    controller._handle_middle_click_mode(15, 20, mouse.Button.middle, False)

    assert len(published) == 4
    assert '"type":"stroke_start"' in published[0]
    assert '"type":"stroke_point"' in published[1]
    assert '"type":"stroke_point"' in published[2]
    assert '"type":"stroke_end"' in published[3]


def test_middle_click_does_not_draw_when_input_disabled() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 10),
        input_enabled_provider=lambda: False,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    controller._handle_middle_click_mode(10, 10, mouse.Button.middle, True)
    controller._on_move(15, 20)
    controller._handle_middle_click_mode(15, 20, mouse.Button.middle, False)

    assert published == []


def test_text_mode_does_not_toggle_when_input_disabled() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 20),
        input_enabled_provider=lambda: False,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    controller._toggle_text_mode()

    assert controller.text_mode_active is False
    assert published == []


def test_windows_text_toggle_uses_alt_modifier() -> None:
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 10),
        input_enabled_provider=lambda: True,
        publish=lambda payload: None,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    original_platform = __import__("crossping.input_hook", fromlist=["sys"]).sys.platform
    __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = "win32"
    try:
        controller.alt_down = True
        controller.ctrl_down = False
        assert controller._text_toggle_modifier_active() is True
    finally:
        __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = original_platform


def test_win32_keyboard_filter_toggles_text_mode_with_alt_1() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 20),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    original_platform = __import__("crossping.input_hook", fromlist=["sys"]).sys.platform
    __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = "win32"
    try:
        controller._win32_keyboard_filter(0x0104, SimpleNamespace(vkCode=0x12))
        controller._win32_keyboard_filter(0x0104, SimpleNamespace(vkCode=0x31))
        controller._win32_keyboard_filter(0x0105, SimpleNamespace(vkCode=0x31))
        controller._win32_keyboard_filter(0x0105, SimpleNamespace(vkCode=0x12))
    finally:
        __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = original_platform

    assert controller.text_mode_active is True
    assert any('"type":"text_start"' in payload for payload in published)


def test_win32_keyboard_filter_publishes_text_updates_while_typing() -> None:
    published = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (10, 20),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    original_platform = __import__("crossping.input_hook", fromlist=["sys"]).sys.platform
    __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = "win32"
    try:
        controller._win32_keyboard_filter(0x0104, SimpleNamespace(vkCode=0x12))
        controller._win32_keyboard_filter(0x0104, SimpleNamespace(vkCode=0x31))
        controller._win32_keyboard_filter(0x0105, SimpleNamespace(vkCode=0x31))
        controller._win32_keyboard_filter(0x0105, SimpleNamespace(vkCode=0x12))
        controller._win32_keyboard_filter(0x0100, SimpleNamespace(vkCode=0x41))
    finally:
        __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = original_platform

    assert any('"type":"text_update"' in payload for payload in published)
    assert '"text":"a"' in published[-1]


def test_win32_mouse_filter_handles_middle_click_when_suppressed() -> None:
    published = []
    pointer = {"x": 10, "y": 10}
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (100, 100),
        pointer_position_provider=lambda: (pointer["x"], pointer["y"]),
        input_enabled_provider=lambda: True,
        publish=published.append,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    original_platform = __import__("crossping.input_hook", fromlist=["sys"]).sys.platform
    __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = "win32"
    try:
        controller._win32_mouse_filter(0x0207, SimpleNamespace(pt=SimpleNamespace(x=10, y=10)))
        assert controller.middle_button_down is True
        pointer["x"] = 15
        pointer["y"] = 20
        controller._on_move(15, 20)
        controller._win32_mouse_filter(0x0208, SimpleNamespace(pt=SimpleNamespace(x=15, y=20)))
        assert controller.middle_button_down is False
    finally:
        __import__("crossping.input_hook", fromlist=["sys"]).sys.platform = original_platform

    assert any('"type":"stroke_start"' in payload for payload in published)
    assert any('"type":"stroke_end"' in payload for payload in published)
