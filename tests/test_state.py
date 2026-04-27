from crossping.state import StrokeStore


def test_clear_logic_targets_only_selected_sender() -> None:
    store = StrokeStore()
    store.start_stroke("alice", "a1")
    store.add_point("alice", "a1", 0.1, 0.2)
    store.start_stroke("bob", "b1")
    store.add_point("bob", "b1", 0.3, 0.4)

    store.clear_sender("alice")

    assert [stroke.sender_id for stroke in store.all_strokes()] == ["bob"]


def test_add_point_creates_stroke_when_missing() -> None:
    store = StrokeStore()
    stroke = store.add_point("alice", "s1", 0.4, 0.5, color="#24c8ff")
    assert stroke is not None
    assert stroke.points == [(0.4, 0.5)]
    assert stroke.color == "#24c8ff"


def test_clear_all_removes_every_sender_and_sender_ids_tracks_visible_drawers() -> None:
    store = StrokeStore()
    store.add_point("alice", "a1", 0.1, 0.2)
    store.add_point("bob", "b1", 0.3, 0.4)

    assert store.sender_ids() == ["alice", "bob"]

    store.clear_all()

    assert store.sender_ids() == []
    assert store.all_strokes() == []
