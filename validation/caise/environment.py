"""Read validation and monitoring configuration from the environment."""

import os
import typing

CAISE_SERVICE_NAME: typing.Final[str] = os.getenv("CAISE_SERVICE_NAME", "")
CAISE_SERVICE_INSTANCE: typing.Final[str] = os.getenv(
    "CAISE_SERVICE_INSTANCE", ""
)
CAISE_SERVICE_URL: typing.Final[str] = os.getenv("CAISE_SERVICE_URL", "")
CAISE_SERVICE_TEST: typing.Final[str] = os.getenv("CAISE_SERVICE_TEST", "")
CAISE_SERVICE_KUBERNETES_RESOURCE: typing.Final[str] = os.getenv(
    "CAISE_SERVICE_KUBERNETES_RESOURCE", ""
)

CAISE_API_USERNAME: typing.Final[str] = os.getenv("CAISE_API_USERNAME", "")
CAISE_API_TOKEN: typing.Final[str] = os.getenv("CAISE_API_TOKEN", "")

CAISE_MONITORING_ENDPOINT: typing.Final[str] = os.getenv(
    "CAISE_MONITORING_ENDPOINT", ""
)
CAISE_MONITORING_USERNAME: typing.Final[str] = os.getenv(
    "CAISE_MONITORING_USERNAME", ""
)
CAISE_MONITORING_PASSWORD: typing.Final[str] = os.getenv(
    "CAISE_MONITORING_PASSWORD", ""
)
