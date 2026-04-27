from crossping.input_hook import GlobalInputController


def test_draw_mode_callback_tracks_modifier_state_changes() -> None:
    changes = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
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


def test_middle_click_mode_only_arms_on_shift() -> None:
    changes = []
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
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

    assert changes == [True, False]


def test_windows_middle_click_suppression_rules() -> None:
    controller = GlobalInputController(
        sender_id="sender",
        screen_size_provider=lambda: (1920, 1080),
        publish=lambda payload: None,
        on_local_clear=lambda: None,
        on_draw_mode_changed=lambda active: None,
        color_provider=lambda: "#ff3366",
        activation_mode="middle_click",
    )

    assert controller._should_suppress_windows_message(0x0207) is True
    assert controller._should_suppress_windows_message(0x0208) is True
    assert controller._should_suppress_windows_message(0x0200) is False

    controller.active_stroke_id = "stroke-1"
    assert controller._should_suppress_windows_message(0x0200) is True
