from crossping.protocol import (
    ClearSenderMessage,
    PingMessage,
    StrokeEndMessage,
    StrokePointMessage,
    StrokeStartMessage,
    decode_message,
    denormalize_point,
    normalize_point,
    topic_for_room,
)


def test_topic_for_room() -> None:
    assert topic_for_room("Alpha 99") == "crossping/alpha99"
    assert topic_for_room("") == "crossping/67"


def test_message_encode_decode() -> None:
    messages = [
        StrokeStartMessage.build("sender", "stroke"),
        StrokePointMessage.build("sender", "stroke", 1.5, -0.2),
        StrokeEndMessage.build("sender", "stroke"),
        ClearSenderMessage.build("sender"),
        PingMessage.build("sender", 0.25, 0.75, color="#24c8ff"),
    ]
    decoded = [decode_message(message.encode()) for message in messages]
    assert [item["type"] for item in decoded] == [
        "stroke_start",
        "stroke_point",
        "stroke_end",
        "clear_sender",
        "ping",
    ]
    assert decoded[1]["x"] == 1.0
    assert decoded[1]["y"] == 0.0
    assert decoded[4]["x"] == 0.25
    assert decoded[4]["y"] == 0.75
    assert decoded[4]["color"] == "#24c8ff"


def test_normalize_and_denormalize_bounds() -> None:
    x, y = normalize_point(500, 1200, 200, 400)
    assert (x, y) == (1.0, 1.0)
    px, py = denormalize_point(-0.5, 0.25, 1920, 1080)
    assert (px, py) == (0.0, 270.0)


def test_primary_desktop_scaling_stays_proportional_across_resolutions() -> None:
    normalized = normalize_point(480, 270, 1920, 1080)
    assert normalized == (0.25, 0.25)

    rendered = denormalize_point(normalized[0], normalized[1], 2560, 1440)
    assert rendered == (640.0, 360.0)
