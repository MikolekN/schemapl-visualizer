"""Test the hand-off to the reference extractor."""

import json

import pytest
from pytest_mock import MockerFixture, MockType
from refextractor import RefExtractor, _result_path, load_ref_service
from settings import Settings
from upstream import HttpFileService, UpstreamError

BASE_URL = "https://refextractor.example/xml-to-xml"


def _envelope(url: str) -> bytes:
    return json.dumps({"xml_file_url": url}).encode()


@pytest.fixture
def upstream(mocker: MockerFixture) -> MockType:
    """Provides a mock of the extractor's HTTP endpoint.

    Returns:
        A mock answering the POST with a result address.
    """
    mock = mocker.Mock(spec=HttpFileService)
    mock.url = BASE_URL
    mock.deployment = "service"
    mock.describe_auth.return_value = "bez nagłówka Authorization"
    mock.send.return_value = _envelope(
        "https://refextractor.example/out/1.xml"
    )
    return mock


def test_result_path_keeps_the_query() -> None:
    """Takes the path and query of the result address."""
    path = _result_path(
        _envelope("https://refextractor.example/out/1.xml?v=2"), BASE_URL
    )

    assert path == "/out/1.xml?v=2"


def test_result_path_on_another_host() -> None:
    """Fetches from the extractor whatever host the address names."""
    assert (
        _result_path(_envelope("http://internal:8000/out/1.xml"), BASE_URL)
        == "/out/1.xml"
    )


def test_reply_that_is_not_json() -> None:
    """Rejects a reply that is not JSON."""
    with pytest.raises(UpstreamError, match="nie JSON"):
        _result_path(b"<html>", BASE_URL)


def test_reply_without_result_address() -> None:
    """Names the fields of a reply that lacks the result address."""
    with pytest.raises(UpstreamError, match="pola: status"):
        _result_path(b'{"status": "ok"}', BASE_URL)


def test_send_returns_the_result(upstream: MockType) -> None:
    """Posts the document and fetches the XML it was turned into."""
    upstream.fetch.return_value = b"<akt-z-odeslaniami/>"
    extractor = RefExtractor(upstream, delay=0)

    result = extractor.send(
        b"<akt/>", filename="akt.xml", authorization="Bearer t"
    )

    assert result == b"<akt-z-odeslaniami/>"
    upstream.send.assert_called_once_with(
        b"<akt/>", filename="akt.xml", authorization="Bearer t"
    )
    upstream.fetch.assert_called_once_with(
        "/out/1.xml", authorization="Bearer t"
    )
    assert extractor.url == BASE_URL
    assert extractor.deployment == "service"


def test_waits_while_the_result_is_missing(upstream: MockType) -> None:
    """Asks again while the result is still a 404."""
    upstream.fetch.side_effect = [
        UpstreamError("404", status=404),
        UpstreamError("404", status=404),
        b"<akt/>",
    ]

    assert (
        RefExtractor(upstream, delay=0).send(b"x", filename="a.xml")
        == b"<akt/>"
    )
    assert upstream.fetch.call_count == 3


def test_gives_up_after_the_last_attempt(upstream: MockType) -> None:
    """Makes a last attempt after the retries and raises its error."""
    upstream.fetch.side_effect = UpstreamError("404", status=404)

    with pytest.raises(UpstreamError):
        RefExtractor(upstream, retries=2, delay=0).send(b"x", filename="a.xml")

    assert upstream.fetch.call_count == 3


def test_other_errors_are_not_retried(upstream: MockType) -> None:
    """Fails at once on errors other than 404."""
    upstream.fetch.side_effect = UpstreamError("500", status=500)

    with pytest.raises(UpstreamError):
        RefExtractor(upstream, delay=0).send(b"x", filename="a.xml")

    assert upstream.fetch.call_count == 1


def test_load_ref_service() -> None:
    """Configures the extractor from the settings."""
    settings = Settings(
        _env_file=None, run_local=False, ref_service_field="dokument"
    )

    extractor = load_ref_service(settings)

    assert extractor.deployment == "service"
    assert extractor.upstream.field_name == "dokument"
    assert extractor.describe_auth() == "bez nagłówka Authorization"
