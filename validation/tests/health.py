"""Check whether key service endpoints are available."""

import logging
import pathlib
import typing

import caise.http

logger = logging.getLogger(__name__)

TEST_ACT: typing.Final[pathlib.Path] = (
    pathlib.Path(__file__).resolve().parent / "h_test.xml"
)


def test_landing_page() -> bool:
    """Check whether the upload page responds with HTTP 200.

    Returns:
        True when the response status is HTTP 200; otherwise False.
    """
    status_code = caise.http.request("/").status_code
    logger.info("Got status code HTTP %d for path /", status_code)
    return status_code == 200


def test_conversion() -> bool:
    """Check whether a sample act converts to HTML.

    The conversion skips the reference lookup, so the check depends on
    this service alone.

    Returns:
        True when the response status is HTTP 200; otherwise False.
    """
    status_code = caise.http.request(
        "/convert/no-refs",
        method="post",
        files={"file": (TEST_ACT.name, TEST_ACT.read_bytes())},
        data={"output": "html"},
    ).status_code
    logger.info(
        "Got status code HTTP %d for path /convert/no-refs", status_code
    )
    return status_code == 200


def run() -> float:
    """Check the landing page and one conversion request.

    Returns:
        1.0 when both endpoints return HTTP 200; otherwise 0.0.
    """
    live = test_landing_page()
    ready = test_conversion()

    if live and ready:
        return 1.0

    return 0.0
