from pathlib import Path

from crossping.config import AppConfig, default_config_path, generate_sender_id, normalize_room_code


def test_normalize_room_code() -> None:
    assert normalize_room_code(" Team-42 !! ") == "team42"
    assert normalize_room_code("") == "67"


def test_generate_sender_id_is_stable_once_persisted(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig.load(path)
    assert config.sender_id
    again = AppConfig.load(path)
    assert again.sender_id == config.sender_id
    assert all(ch.islower() or ch.isdigit() for ch in again.sender_id)


def test_save_normalizes_room_code(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig(room_code=" My Room ", activation_mode="middle_click", color="#24c8ff", sender_id=generate_sender_id())
    config.save(path)
    loaded = AppConfig.load(path)
    assert loaded.room_code == "myroom"
    assert loaded.activation_mode == "middle_click"
    assert loaded.color == "#24c8ff"


def test_default_config_path_honors_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CROSSPING_CONFIG_DIR", str(tmp_path))
    assert default_config_path() == tmp_path / "config.json"
