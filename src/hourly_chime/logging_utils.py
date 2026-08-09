from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import paths


def get_logger(name: str = "hourly_chime") -> logging.Logger:
    paths.ensure_layout()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        paths.log_dir() / "hourly-chime.log",
        maxBytes=1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
