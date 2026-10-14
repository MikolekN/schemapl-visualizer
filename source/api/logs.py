"""Log configuration for the service."""

from __future__ import annotations

import logging
import sys

# The service's own loggers. Its modules are top-level modules, so
# they share no parent logger: each is configured by name.
LOGGER_NAMES = (
    "main",
    "upstream",
    "refextractor",
    "d2xconverter",
    "schemapl_visualizer",
)
DEFAULT_LEVEL = "INFO"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
HANDLER_NAME = "service-stdout"


def configure_logging(level: str | None = None) -> None:
    """Send our logs to stdout at ``level`` (default INFO).

    ``level`` is the ``LOG_LEVEL`` setting. uvicorn only sets up
    handlers for its own loggers, so ours need their own. stdout
    because that is where uvicorn's access log goes — a log viewer
    showing only one stream then shows ours too. ``DEBUG`` adds
    request and response headers as well.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(FORMAT))
    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.setLevel(_level(level))
        if not any(
            existing.get_name() == HANDLER_NAME for existing in logger.handlers
        ):
            logger.addHandler(handler)
        logger.propagate = False


def _level(name: str | None) -> int:
    level = logging.getLevelName((name or DEFAULT_LEVEL).strip().upper())
    return level if isinstance(level, int) else logging.INFO
