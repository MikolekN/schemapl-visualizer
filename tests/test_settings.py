"""Test the service settings and logging configuration."""

import logging
from pathlib import Path

import pytest
from logs import HANDLER_NAME, LOGGER_NAMES, configure_logging
from settings import Settings

VARIABLES = (
    "RUN_LOCAL",
    "SERVICE_USER",
    "SERVICE_PASSWORD",
    "REF_SERVICE_FIELD",
    "DOCX_SERVICE_FIELD",
    "DOCX_EXPERIMENTAL_SERVICE_FIELD",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Removes the service variables a developer may have set."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_defaults() -> None:
    """Reaches the services internally and without credentials."""
    settings = Settings(_env_file=None)

    assert settings.run_local is False
    assert settings.service_user is None
    assert settings.password is None
    assert settings.ref_service_field == "file"
    assert settings.docx_service_field == "docxFile"
    assert settings.docx_experimental_service_field == "documentFile"
    assert settings.log_level == "INFO"


def test_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads every field from its upper-case environment variable."""
    monkeypatch.setenv("RUN_LOCAL", "true")
    monkeypatch.setenv("SERVICE_USER", "user")
    monkeypatch.setenv("SERVICE_PASSWORD", "secret")
    monkeypatch.setenv("DOCX_SERVICE_FIELD", "plik")
    monkeypatch.setenv("DOCX_EXPERIMENTAL_SERVICE_FIELD", "dokument")

    settings = Settings(_env_file=None)

    assert settings.run_local is True
    assert settings.service_user == "user"
    assert settings.password == "secret"  # noqa: S105 - test value
    assert "secret" not in repr(settings)
    assert settings.docx_service_field == "plik"
    assert settings.docx_experimental_service_field == "dokument"


def test_empty_variables_keep_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treats an empty variable, such as ``RUN_LOCAL=``, as unset."""
    monkeypatch.setenv("RUN_LOCAL", "")
    monkeypatch.setenv("SERVICE_USER", "")

    settings = Settings(_env_file=None)

    assert settings.run_local is False
    assert settings.service_user is None


def test_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reads a .env file, letting the environment take precedence."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RUN_LOCAL=1\nSERVICE_USER=from-file\n", encoding="utf-8"
    )
    monkeypatch.setenv("SERVICE_USER", "from-environment")

    settings = Settings(_env_file=env_file)

    assert settings.run_local is True
    assert settings.service_user == "from-environment"


def test_log_level() -> None:
    """Sets the service loggers to the configured level."""
    configure_logging("debug")

    assert all(
        logging.getLogger(name).level == logging.DEBUG for name in LOGGER_NAMES
    )

    configure_logging("nonsense")

    assert logging.getLogger("main").level == logging.INFO


def test_one_handler_per_logger() -> None:
    """Adds no second handler when configured again."""
    configure_logging()
    configure_logging()

    handlers = logging.getLogger("upstream").handlers
    assert [handler.get_name() for handler in handlers].count(
        HANDLER_NAME
    ) == 1
