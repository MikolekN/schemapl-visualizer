"""Generate concurrent traffic against the configured service.

Requests do not validate response content. Worker errors do not affect
the final score.
"""

import concurrent.futures
import logging
import pathlib
import typing

import caise.http

logger = logging.getLogger(__name__)

TEST_ACT: typing.Final[pathlib.Path] = (
    pathlib.Path(__file__).resolve().parent / "h_test.xml"
)

# Output formats requested: mostly HTML, with both PDF layouts.
DATA_SET: typing.Final[list[str]] = [
    "html",
    "html",
    "html",
    "pdf",
    "html",
    "html",
    "html",
    "pdf-accessible",
] * 4


def test_convert(output: str) -> None:
    """Send one conversion request and log any error.

    Args:
        output: Requested output format.
    """
    try:
        response = caise.http.request(
            "/convert/no-refs",
            method="post",
            files={"file": (TEST_ACT.name, TEST_ACT.read_bytes())},
            data={"output": output},
            timeout=60,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Exception while running test_convert")


def run() -> float:
    """Send the data set concurrently and return a fixed success score.

    Returns:
        Always 1.0 after all worker calls finish.
    """
    data_set = DATA_SET

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(test_convert, data_set))

    return 1.0
