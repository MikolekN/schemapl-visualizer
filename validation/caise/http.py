"""Provide an HTTP client for the service under validation."""

from typing import Any

import requests

import caise.environment


def request(
    path: str,
    method: str = "get",
    **kwargs: Any,  # noqa: ANN401 - forwards Requests options of different types.
) -> requests.Response:
    """Sends an authenticated request to the configured service.

    Args:
        path: Path appended to the configured service URL.
        method: HTTP method accepted by `requests.request`.
        **kwargs: Additional arguments forwarded to `requests.request`.

    Returns:
        The response returned by Requests.
    """
    timeout = kwargs.pop("timeout", 20)
    return requests.request(
        method,
        f"{caise.environment.CAISE_SERVICE_URL}{path}",
        auth=(
            caise.environment.CAISE_API_USERNAME,
            caise.environment.CAISE_API_TOKEN,
        ),
        timeout=timeout,
        **kwargs,
    )
