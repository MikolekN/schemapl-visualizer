"""Compare live conversion results with what the sample act contains."""

import logging
import pathlib
import typing

import caise.http

logger = logging.getLogger(__name__)

TEST_ACT: typing.Final[pathlib.Path] = (
    pathlib.Path(__file__).resolve().parent / "h_test.xml"
)

# Text of the sample act every HTML conversion must contain.
EXPECTED_PHRASES: typing.Final[list[str]] = [
    "Obwieszczenie Marszałka Sejmu",
    "z dnia 1 września 2026 r.",
    "jednolitego tekstu ustawy",
    "Kodeks wyborczy",
    "Dział I",
    "Rozdział 1",
    "Przepisy ogólne",
    "Art. 1.",
    "Dz. U. z 2025 r. poz. 365",
]


def convert(output: str) -> bytes | None:
    """Convert the sample act without the reference lookup.

    Args:
        output: Requested output format.

    Returns:
        The response body, or None when the request fails.
    """
    try:
        response = caise.http.request(
            "/convert/no-refs",
            method="post",
            files={"file": (TEST_ACT.name, TEST_ACT.read_bytes())},
            data={"output": output},
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Exception while converting to %s", output)
        return None
    return response.content


def test_html() -> list[bool]:
    """Check the HTML view for each expected phrase.

    Returns:
        One result per expected phrase.
    """
    content = convert("html")
    if content is None:
        return [False] * len(EXPECTED_PHRASES)
    text = content.decode("utf-8", "replace")
    results = [phrase in text for phrase in EXPECTED_PHRASES]
    for phrase, found in zip(EXPECTED_PHRASES, results, strict=True):
        if not found:
            logger.warning("HTML lacks the phrase %r", phrase)
    return results


def test_pdf(output: str, marker: bytes) -> bool:
    """Check that a PDF layout is produced and carries a marker.

    Args:
        output: Requested PDF format.
        marker: Bytes the PDF must contain.

    Returns:
        True when the response is a PDF containing the marker.
    """
    content = convert(output)
    passed = (
        content is not None
        and content.startswith(b"%PDF-")
        and marker in content
    )
    if not passed:
        logger.warning("%s output failed the check", output)
    return passed


def run() -> float:
    """Run all sample checks and return their success ratio.

    Returns:
        The ratio of successful checks to all checks.
    """
    results = [
        *test_html(),
        test_pdf("pdf", b"/Type"),
        # The accessible layout is tagged as PDF/UA.
        test_pdf("pdf-accessible", b"pdfuaid"),
    ]
    return sum(results) / len(results)
