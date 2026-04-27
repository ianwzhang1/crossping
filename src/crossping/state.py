from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Stroke:
    sender_id: str
    stroke_id: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#ff3366"
    width: float = 3.0
    active: bool = True


@dataclass
class Ping:
    sender_id: str
    x: float
    y: float
    timestamp: float
    color: str = "#ff3366"


class StrokeStore:
    def __init__(self) -> None:
        self._strokes: Dict[str, Dict[str, Stroke]] = {}

    def start_stroke(self, sender_id: str, stroke_id: str, color: str = "#ff3366", width: float = 3.0) -> Stroke:
        sender_strokes = self._strokes.setdefault(sender_id, {})
        stroke = Stroke(sender_id=sender_id, stroke_id=stroke_id, color=color, width=width)
        sender_strokes[stroke_id] = stroke
        return stroke

    def add_point(self, sender_id: str, stroke_id: str, x: float, y: float) -> Optional[Stroke]:
        stroke = self._strokes.get(sender_id, {}).get(stroke_id)
        if stroke is None:
            stroke = self.start_stroke(sender_id, stroke_id)
        stroke.points.append((x, y))
        return stroke

    def end_stroke(self, sender_id: str, stroke_id: str) -> None:
        stroke = self._strokes.get(sender_id, {}).get(stroke_id)
        if stroke is not None:
            stroke.active = False

    def clear_sender(self, sender_id: str) -> None:
        self._strokes.pop(sender_id, None)

    def all_strokes(self) -> List[Stroke]:
        strokes: List[Stroke] = []
        for sender_strokes in self._strokes.values():
            strokes.extend(sender_strokes.values())
        return strokes

    def sender_strokes(self, sender_id: str) -> List[Stroke]:
        return list(self._strokes.get(sender_id, {}).values())
