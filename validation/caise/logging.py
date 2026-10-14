"""Configure logging for validation runs."""

import logging


def configure() -> None:
    """Configure validation logging at INFO level."""
    logging.basicConfig(
        format="{asctime} {levelname} [{name}]: {message}",
        level="INFO",
        style="{",
    )
