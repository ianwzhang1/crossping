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


@dataclass
class TextAnnotation:
    sender_id: str
    text_id: str
    x: float
    y: float
    text: str = ""
    color: str = "#ff3366"
    active: bool = True


class StrokeStore:
    def __init__(self) -> None:
        self._strokes: Dict[str, Dict[str, Stroke]] = {}
        self._texts: Dict[str, Dict[str, TextAnnotation]] = {}

    def start_stroke(self, sender_id: str, stroke_id: str, color: str = "#ff3366", width: float = 3.0) -> Stroke:
        sender_strokes = self._strokes.setdefault(sender_id, {})
        stroke = Stroke(sender_id=sender_id, stroke_id=stroke_id, color=color, width=width)
        sender_strokes[stroke_id] = stroke
        return stroke

    def add_point(self, sender_id: str, stroke_id: str, x: float, y: float, color: str = "#ff3366") -> Optional[Stroke]:
        stroke = self._strokes.get(sender_id, {}).get(stroke_id)
        if stroke is None:
            stroke = self.start_stroke(sender_id, stroke_id, color=color)
        else:
            stroke.color = color
        stroke.points.append((x, y))
        return stroke

    def end_stroke(self, sender_id: str, stroke_id: str) -> None:
        stroke = self._strokes.get(sender_id, {}).get(stroke_id)
        if stroke is not None:
            stroke.active = False

    def clear_sender(self, sender_id: str) -> None:
        self._strokes.pop(sender_id, None)
        self._texts.pop(sender_id, None)

    def clear_all(self) -> None:
        self._strokes.clear()
        self._texts.clear()

    def start_text(self, sender_id: str, text_id: str, x: float, y: float, color: str = "#ff3366") -> TextAnnotation:
        sender_texts = self._texts.setdefault(sender_id, {})
        text_annotation = TextAnnotation(sender_id=sender_id, text_id=text_id, x=x, y=y, color=color)
        sender_texts[text_id] = text_annotation
        return text_annotation

    def update_text(self, sender_id: str, text_id: str, text: str, color: str = "#ff3366") -> Optional[TextAnnotation]:
        text_annotation = self._texts.get(sender_id, {}).get(text_id)
        if text_annotation is None:
            text_annotation = self.start_text(sender_id, text_id, 0.0, 0.0, color=color)
        text_annotation.text = text
        text_annotation.color = color
        return text_annotation

    def end_text(self, sender_id: str, text_id: str) -> None:
        text_annotation = self._texts.get(sender_id, {}).get(text_id)
        if text_annotation is not None:
            text_annotation.active = False

    def all_strokes(self) -> List[Stroke]:
        strokes: List[Stroke] = []
        for sender_strokes in self._strokes.values():
            strokes.extend(sender_strokes.values())
        return strokes

    def all_text_annotations(self) -> List[TextAnnotation]:
        text_annotations: List[TextAnnotation] = []
        for sender_texts in self._texts.values():
            text_annotations.extend(sender_texts.values())
        return text_annotations

    def sender_strokes(self, sender_id: str) -> List[Stroke]:
        return list(self._strokes.get(sender_id, {}).values())

    def sender_ids(self) -> List[str]:
        return sorted(set(self._strokes.keys()) | set(self._texts.keys()))
