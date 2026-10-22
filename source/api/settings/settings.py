"""Define settings for the schemaPL visualizer service."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load service configuration from environment variables.

    Each field is read from the variable of the same name in upper case
    (``RUN_LOCAL``, ``SERVICE_USER``, ...). Locally the variables can
    also come from a ``.env`` file in the directory the service is
    started from; variables set in the environment take precedence.
    """

    # Upstream services: reference extractor and DOCX → XML converter.
    # Set: reach them over the public route, which needs credentials.
    # Unset: reach them by their internal service names.
    run_local: bool = False
    service_user: str | None = None
    service_password: SecretStr | None = None

    # Form field names the upstream services expect the file under.
    ref_service_field: str = "file"
    docx_service_field: str = "docxFile"
    docx_experimental_service_field: str = "documentFile"

    # DEBUG adds the request and response headers of upstream calls.
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def password(self) -> str | None:
        """Return the upstream password as plain text, if one is set."""
        if self.service_password is None:
            return None
        return self.service_password.get_secret_value()


settings = Settings()
