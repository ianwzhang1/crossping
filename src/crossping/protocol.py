from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Dict, Tuple, Union

TOPIC_PREFIX = "crossping"
DEFAULT_ROOM_CODE = "67"


def topic_for_room(room_code: str) -> str:
    normalized = "".join(ch.lower() for ch in room_code if ch.isalnum()) or DEFAULT_ROOM_CODE
    return f"{TOPIC_PREFIX}/{normalized}"


def clamp_normalized(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_point(x: float, y: float, width: float, height: float) -> Tuple[float, float]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    return clamp_normalized(x / width), clamp_normalized(y / height)


def denormalize_point(x: float, y: float, width: float, height: float) -> Tuple[float, float]:
    return clamp_normalized(x) * width, clamp_normalized(y) * height


@dataclass
class BaseMessage:
    type: str
    sender_id: str
    timestamp: float

    def encode(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


@dataclass
class StrokeStartMessage(BaseMessage):
    stroke_id: str
    color: str = "#ff3366"
    width: float = 3.0

    @classmethod
    def build(cls, sender_id: str, stroke_id: str, color: str = "#ff3366", width: float = 3.0) -> "StrokeStartMessage":
        return cls(type="stroke_start", sender_id=sender_id, timestamp=time.time(), stroke_id=stroke_id, color=color, width=width)


@dataclass
class StrokePointMessage(BaseMessage):
    stroke_id: str
    x: float
    y: float
    color: str = "#ff3366"

    @classmethod
    def build(cls, sender_id: str, stroke_id: str, x: float, y: float, color: str = "#ff3366") -> "StrokePointMessage":
        return cls(type="stroke_point", sender_id=sender_id, timestamp=time.time(), stroke_id=stroke_id, x=clamp_normalized(x), y=clamp_normalized(y), color=color)


@dataclass
class StrokeEndMessage(BaseMessage):
    stroke_id: str

    @classmethod
    def build(cls, sender_id: str, stroke_id: str) -> "StrokeEndMessage":
        return cls(type="stroke_end", sender_id=sender_id, timestamp=time.time(), stroke_id=stroke_id)


@dataclass
class ClearSenderMessage(BaseMessage):
    @classmethod
    def build(cls, sender_id: str) -> "ClearSenderMessage":
        return cls(type="clear_sender", sender_id=sender_id, timestamp=time.time())


@dataclass
class ClearAllMessage(BaseMessage):
    @classmethod
    def build(cls, sender_id: str) -> "ClearAllMessage":
        return cls(type="clear_all", sender_id=sender_id, timestamp=time.time())


@dataclass
class TextStartMessage(BaseMessage):
    text_id: str
    x: float
    y: float
    color: str = "#ff3366"

    @classmethod
    def build(cls, sender_id: str, text_id: str, x: float, y: float, color: str = "#ff3366") -> "TextStartMessage":
        return cls(
            type="text_start",
            sender_id=sender_id,
            timestamp=time.time(),
            text_id=text_id,
            x=clamp_normalized(x),
            y=clamp_normalized(y),
            color=color,
        )


@dataclass
class TextUpdateMessage(BaseMessage):
    text_id: str
    text: str
    color: str = "#ff3366"

    @classmethod
    def build(cls, sender_id: str, text_id: str, text: str, color: str = "#ff3366") -> "TextUpdateMessage":
        return cls(type="text_update", sender_id=sender_id, timestamp=time.time(), text_id=text_id, text=text, color=color)


@dataclass
class TextEndMessage(BaseMessage):
    text_id: str

    @classmethod
    def build(cls, sender_id: str, text_id: str) -> "TextEndMessage":
        return cls(type="text_end", sender_id=sender_id, timestamp=time.time(), text_id=text_id)


@dataclass
class PingMessage(BaseMessage):
    x: float
    y: float
    color: str = "#ff3366"

    @classmethod
    def build(cls, sender_id: str, x: float, y: float, color: str = "#ff3366") -> "PingMessage":
        return cls(type="ping", sender_id=sender_id, timestamp=time.time(), x=clamp_normalized(x), y=clamp_normalized(y), color=color)


Message = Union[
    StrokeStartMessage,
    StrokePointMessage,
    StrokeEndMessage,
    ClearSenderMessage,
    ClearAllMessage,
    TextStartMessage,
    TextUpdateMessage,
    TextEndMessage,
    PingMessage,
]


def decode_message(payload: Union[str, bytes]) -> Dict[str, object]:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)
