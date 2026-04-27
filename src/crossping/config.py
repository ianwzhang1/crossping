from __future__ import annotations

import json
import os
import secrets
import string
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

APP_DIR_NAME = "crossping"
DEFAULT_BROKER_HOST = "broker.hivemq.com"
DEFAULT_BROKER_PORT = 1883
DEFAULT_ROOM_CODE = "67"
DEFAULT_ACTIVATION_MODE = "middle_click"
ACTIVATION_MODES = ("middle_click", "ctrl_shift")
DEFAULT_COLOR = "#ff3366"
COLOR_OPTIONS = (
    ("#ff3366", "Rose"),
    ("#24c8ff", "Cyan"),
    ("#7dff7a", "Lime"),
    ("#ffd166", "Gold"),
    ("#c792ea", "Lavender"),
)
ROOM_CODE_ALPHABET = string.ascii_lowercase + string.digits


CONFIG_DIR_ENV_VAR = "CROSSPING_CONFIG_DIR"


def default_config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base_dir / APP_DIR_NAME
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / APP_DIR_NAME
    return Path.home() / ".config" / APP_DIR_NAME


def default_config_path() -> Path:
    return default_config_dir() / "config.json"


def normalize_room_code(room_code: str) -> str:
    cleaned = "".join(ch.lower() for ch in room_code if ch.isalnum())
    return cleaned or DEFAULT_ROOM_CODE


def generate_sender_id(length: int = 16) -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))


@dataclass
class AppConfig:
    room_code: str = DEFAULT_ROOM_CODE
    broker_host: str = DEFAULT_BROKER_HOST
    broker_port: int = DEFAULT_BROKER_PORT
    activation_mode: str = DEFAULT_ACTIVATION_MODE
    color: str = DEFAULT_COLOR
    sender_id: str = ""

    def normalized_room_code(self) -> str:
        return normalize_room_code(self.room_code)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        config_path = path or default_config_path()
        if not config_path.exists():
            config = cls(sender_id=generate_sender_id())
            config.save(config_path)
            return config
        data = json.loads(config_path.read_text(encoding="utf-8"))
        sender_id = data.get("sender_id") or generate_sender_id()
        return cls(
            room_code=data.get("room_code", DEFAULT_ROOM_CODE),
            broker_host=data.get("broker_host", DEFAULT_BROKER_HOST),
            broker_port=int(data.get("broker_port", DEFAULT_BROKER_PORT)),
            activation_mode=data.get("activation_mode", DEFAULT_ACTIVATION_MODE),
            color=data.get("color", DEFAULT_COLOR),
            sender_id=sender_id,
        )

    def save(self, path: Optional[Path] = None) -> None:
        config_path = path or default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = asdict(self)
        payload["room_code"] = self.normalized_room_code()
        config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
