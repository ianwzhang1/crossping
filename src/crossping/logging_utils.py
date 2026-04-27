from __future__ import annotations

import logging
from pathlib import Path

from .config import default_config_dir

LOGGER_NAME = "crossping"


def default_log_path() -> Path:
    return default_config_dir() / "crossping.log"


def setup_logging() -> Path:
    log_path = default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return log_path

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.propagate = False
    logger.debug("logging initialized at %s", log_path)
    return log_path
