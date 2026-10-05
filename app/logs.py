"""Log configuration for the service and the CLI."""

from __future__ import annotations

import logging
import os
import sys

LOGGER_NAME = "app"
DEFAULT_LEVEL = "INFO"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging() -> logging.Logger:
    """Send our logs to stdout at ``LOG_LEVEL`` (default INFO).

    uvicorn only sets up handlers for its own loggers, so ours needs its own.
    stdout because that is where uvicorn's access log goes — a log viewer
    showing only one stream then shows ours too.
    Set ``LOG_LEVEL=DEBUG`` for request and response headers as well.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_level(os.environ.get("LOG_LEVEL")))
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMAT))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def _level(name: str | None) -> int:
    level = logging.getLevelName((name or DEFAULT_LEVEL).strip().upper())
    return level if isinstance(level, int) else logging.INFO
