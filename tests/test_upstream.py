"""Test the HTTP calls to the other CAISE services."""

import email.message
import io
import urllib.error
import urllib.request
from typing import Self

import pytest
from d2xconverter import DOCX_MEDIA_TYPE, load_docx_service
from pytest_mock import MockerFixture, MockType
from settings import Settings
from upstream import (
    Deployment,
    HttpFileService,
    UpstreamError,
    _headers,
    _multipart,
    preview,
    resolve_deployment,
)

URL = "https://service.example/parse"


class FakeResponse:
    """Stands in for the response ``urlopen`` returns."""

    def __init__(self, body: bytes, url: str = URL) -> None:
        """Creates a 200 response with ``body``, sent from ``url``."""
        self._body = body
        self._url = url
        self.status = 200
        self.reason = "OK"
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "application/xml"

    def __enter__(self) -> Self:
        """Returns the response itself."""
        return self

    def __exit__(self, *args: object) -> None:
        """Closes nothing."""

    def read(self) -> bytes:
        """Returns the body."""
        return self._body

    def geturl(self) -> str:
        """Returns the address the response came from."""
        return self._url


def _http_error(
    code: int, body: bytes, **headers: str
) -> urllib.error.HTTPError:
    message = email.message.Message()
    for name, value in headers.items():
        message[name.replace("_", "-")] = value
    return urllib.error.HTTPError(
        URL, code, "Error", message, io.BytesIO(body)
    )


@pytest.fixture
def urlopen(mocker: MockerFixture) -> MockType:
    """Replaces ``urllib.request.urlopen`` with a mock.

    Returns:
        The mock; its calls hold the requests made.
    """
    return mocker.patch(
        "urllib.request.urlopen", return_value=FakeResponse(b"<ok/>")
    )


def _service(**overrides: str) -> HttpFileService:
    values = {
        "url": URL,
        "field_name": "file",
        "media_type": "application/xml",
    }
    return HttpFileService(**(values | overrides))


def _sent(urlopen: MockType) -> urllib.request.Request:
    return urlopen.call_args.args[0]


def test_resolve_deployment() -> None:
    """Chooses the public deployment only when running locally."""
    local = Deployment("local", "https://public.example", "public")
    service = Deployment("service", "http://internal:8000", "internal")

    assert resolve_deployment(local, service, run_local=True) is local
    assert resolve_deployment(local, service, run_local=False) is service


def test_send_posts_the_file(urlopen: MockType) -> None:
    """Posts the file as multipart form data and returns the body."""
    result = _service().send(b"<akt/>", filename="akt.xml")

    request = _sent(urlopen)
    assert result == b"<ok/>"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type").startswith("multipart/form-data")
    assert b'name="file"; filename="akt.xml"' in request.data
    assert b"<akt/>" in request.data
    assert request.get_header("Authorization") is None


def test_basic_credentials(urlopen: MockType) -> None:
    """Authenticates with the configured user and password."""
    service = _service(username="user", password="secret")  # noqa: S106

    service.send(b"x", filename="a.xml")

    assert (
        _sent(urlopen).get_header("Authorization") == "Basic dXNlcjpzZWNyZXQ="
    )
    assert service.describe_auth() == "Basic (użytkownik user)"


def test_client_authorization_takes_precedence(urlopen: MockType) -> None:
    """Forwards the client's Authorization header when there is one."""
    _service(username="user", password="secret").send(  # noqa: S106
        b"x", filename="a.xml", authorization="Bearer token"
    )

    assert _sent(urlopen).get_header("Authorization") == "Bearer token"


def test_no_credentials_described() -> None:
    """Says when calls carry no Authorization header."""
    assert _service().describe_auth() == "bez nagłówka Authorization"


def test_fetch_joins_the_path(urlopen: MockType) -> None:
    """Fetches a path relative to the service address."""
    _service().fetch("/results/1.xml")

    assert _sent(urlopen).full_url == "https://service.example/results/1.xml"


def test_redirect_still_returns_the_body(urlopen: MockType) -> None:
    """Returns the body of a redirected response."""
    urlopen.return_value = FakeResponse(
        b"<ok/>", url="https://elsewhere.example/"
    )

    assert _service().send(b"x", filename="a.xml") == b"<ok/>"


def test_rejected_credentials(urlopen: MockType) -> None:
    """Explains a 401 with what was sent and what the service wants."""
    urlopen.side_effect = _http_error(401, b"", WWW_Authenticate="Basic")

    with pytest.raises(UpstreamError, match="uwierzytelnienie") as caught:
        _service().send(b"x", filename="a.xml")

    assert caught.value.status == 401
    assert "oczekuje: Basic" in str(caught.value)


def test_server_error(urlopen: MockType) -> None:
    """Keeps the status and the first line of the error body."""
    urlopen.side_effect = _http_error(500, b"Internal failure\nTraceback")

    with pytest.raises(UpstreamError, match="Internal failure") as caught:
        _service().send(b"x", filename="a.xml")

    assert caught.value.status == 500


def test_unreachable_service(urlopen: MockType) -> None:
    """Reports a service that cannot be reached."""
    urlopen.side_effect = urllib.error.URLError("Name or service not known")

    with pytest.raises(UpstreamError, match="niedostępna") as caught:
        _service().send(b"x", filename="a.xml")

    assert caught.value.status is None


def test_connection_error(urlopen: MockType) -> None:
    """Reports a connection that broke off."""
    urlopen.side_effect = ConnectionResetError("reset")

    with pytest.raises(UpstreamError, match="błąd połączenia"):
        _service().send(b"x", filename="a.xml")


def test_empty_response(urlopen: MockType) -> None:
    """Treats an empty body as a failure."""
    urlopen.return_value = FakeResponse(b"  ")

    with pytest.raises(UpstreamError, match="pustą odpowiedź"):
        _service().send(b"x", filename="a.xml")


def test_multipart_filename_is_sanitised() -> None:
    """Drops characters that would break the part header."""
    body, content_type = _multipart(
        "file", 'a"b\r\n.xml', b"data", "application/xml"
    )

    assert b'filename="ab.xml"' in body
    assert content_type.startswith("multipart/form-data; boundary=")


def test_preview_is_one_short_line() -> None:
    """Squeezes a body onto one line and shortens it."""
    assert preview(b"a\n  b") == "a b"
    assert preview(b"x" * 600).endswith("…")


def test_authorization_is_hidden_in_logs() -> None:
    """Keeps the Authorization value out of logged headers."""
    logged = _headers([("Authorization", "Basic secret"), ("Accept", "*/*")])

    assert "secret" not in logged
    assert "Accept: */*" in logged


def test_load_docx_service() -> None:
    """Configures the DOCX converter from the settings."""
    settings = Settings(
        _env_file=None,
        run_local=True,
        service_user="user",
        service_password="secret",  # noqa: S106 - test value.
        docx_service_field="plik",
    )

    service = load_docx_service(settings)

    assert service.deployment == "local"
    assert service.url.startswith("https://")
    assert service.field_name == "plik"
    assert service.media_type == DOCX_MEDIA_TYPE
    assert (service.username, service.password) == ("user", "secret")
