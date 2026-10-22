"""Test the HTTP endpoints with the upstream services mocked."""

import httpx2
import main
import pytest
from fastapi import testclient
from pytest_mock import MockerFixture, MockType
from upstream import UpstreamError

from schemapl_visualizer import PdfError

DOCX = b"PK\x03\x04 a DOCX is a ZIP archive"


@pytest.fixture
def ref_service(mocker: MockerFixture, math_act: bytes) -> MockType:
    """Replaces the reference extractor with a mock.

    Returns:
        The mock.
    """
    service = mocker.patch.object(main, "_ref_service")
    service.send.return_value = math_act
    return service


@pytest.fixture
def docx_service(mocker: MockerFixture, math_act: bytes) -> MockType:
    """Replaces the DOCX converter with a mock returning the math act.

    Returns:
        The mock.
    """
    service = mocker.patch.object(main, "_docx_service")
    service.send.return_value = math_act
    return service


@pytest.fixture
def docx_experimental_service(
    mocker: MockerFixture, math_act: bytes
) -> MockType:
    """Replaces the experimental DOCX converter with a mock.

    It returns the math act.

    Returns:
        The mock.
    """
    service = mocker.patch.object(main, "_docx_experimental_service")
    service.send.return_value = math_act
    return service


def _post(
    client: testclient.TestClient,
    path: str,
    content: bytes,
    filename: str = "akt.xml",
    **data: str,
) -> httpx2.Response:
    return client.post(path, files={"file": (filename, content)}, data=data)


def test_index(api_client: testclient.TestClient) -> None:
    """Serves the upload form with the service version."""
    response = api_client.get("/")

    assert response.status_code == 200
    assert 'action="/convert/file"' in response.text
    assert f"wersja {main.__version__}" in response.text
    assert 'name="eksperymentalny"' in response.text


@pytest.mark.usefixtures("ref_service")
@pytest.mark.parametrize("path", ["/convert/file", "/convert/docx"])
def test_experimental_docx_converter(
    api_client: testclient.TestClient,
    docx_service: MockType,
    docx_experimental_service: MockType,
    path: str,
) -> None:
    """Sends a DOCX to the experimental converter when asked."""
    response = _post(
        api_client,
        path,
        DOCX,
        filename="ustawa.docx",
        output="xml",
        eksperymentalny="true",
    )

    assert response.status_code == 200
    sent = docx_experimental_service.send.call_args.kwargs
    assert sent["filename"] == "ustawa.docx"
    docx_service.send.assert_not_called()


def test_experimental_option_leaves_xml_alone(
    api_client: testclient.TestClient, docx_experimental_service: MockType
) -> None:
    """Calls no converter for an XML file, experimental or not."""
    response = _post(
        api_client, "/convert/file", b"<akt/>", eksperymentalny="true"
    )

    assert response.status_code == 200
    docx_experimental_service.send.assert_not_called()


def test_experimental_docx_failure(
    api_client: testclient.TestClient, docx_experimental_service: MockType
) -> None:
    """Names the experimental converter when it fails."""
    docx_experimental_service.send.side_effect = UpstreamError("down")

    response = _post(
        api_client,
        "/convert/file",
        DOCX,
        filename="ustawa.docx",
        eksperymentalny="true",
    )

    assert response.status_code == 400
    assert "nie powiodła się (konwerter eksperymentalny)" in response.text


def test_documented_endpoints(api_client: testclient.TestClient) -> None:
    """Documents the XML and DOCX conversions the service offers."""
    response = api_client.get("/openapi.json")

    assert sorted(response.json()["paths"]) == [
        "/",
        "/convert",
        "/convert/docx",
        "/convert/file",
        "/convert/no-refs",
    ]


def test_logo(api_client: testclient.TestClient) -> None:
    """Serves the CAISE logo."""
    response = api_client.get("/tmp/caise.png")  # noqa: S108 - URL path

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    ("output", "media_type"),
    [("html", "text/html; charset=utf-8"), ("pdf", "application/pdf")],
)
def test_convert_without_references(
    api_client: testclient.TestClient,
    math_act: bytes,
    ref_service: MockType,
    output: str,
    media_type: str,
) -> None:
    """Converts without calling the reference extractor."""
    response = _post(api_client, "/convert/no-refs", math_act, output=output)

    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    ref_service.send.assert_not_called()


def test_pdf_keeps_a_non_ascii_name(
    api_client: testclient.TestClient, math_act: bytes
) -> None:
    """Names the PDF after the uploaded file, in both header forms."""
    response = _post(
        api_client,
        "/convert/no-refs",
        math_act,
        filename="ustawa_ż.xml",
        output="pdf-accessible",
    )

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("inline;")
    assert 'filename="ustawa__.accessible.pdf"' in disposition
    assert "filename*=UTF-8''ustawa_%C5%BC.accessible.pdf" in disposition


def test_convert_looks_up_references(
    api_client: testclient.TestClient, ref_service: MockType
) -> None:
    """Sends the document to the reference extractor first."""
    response = _post(api_client, "/convert", b"<akt/>")

    assert response.status_code == 200
    assert ref_service.send.call_args.args[0] == b"<akt/>"


def test_failed_reference_lookup(
    api_client: testclient.TestClient, ref_service: MockType
) -> None:
    """Explains a failed reference lookup."""
    ref_service.send.side_effect = UpstreamError("timeout")

    response = _post(api_client, "/convert", b"<akt/>")

    assert response.status_code == 400
    assert "Wyszukiwanie odesłań nie powiodło się" in response.text


@pytest.mark.parametrize(
    ("content", "output", "message"),
    [
        (b"<akt>", "html", "Niepoprawny XML"),
        (b'<doc xmlns="urn:example"/>', "pdf", "schemaPL"),
        (b"<a>" * 101 + b"</a>" * 101, "html", "zbyt głęboko"),
        (b"<a>" * 2000 + b"</a>" * 2000, "html", "Niepoprawny XML"),
        (b"<akt/>", "docx", "Nieznany format"),
    ],
)
def test_conversion_errors(
    api_client: testclient.TestClient,
    content: bytes,
    output: str,
    message: str,
) -> None:
    """Answers 400 with a readable message."""
    response = _post(api_client, "/convert/no-refs", content, output=output)

    assert response.status_code == 400
    assert message in response.text


def test_typesetting_error(
    api_client: testclient.TestClient, mocker: MockerFixture, math_act: bytes
) -> None:
    """Explains a PDF that Typst could not typeset."""
    mocker.patch.object(
        main, "convert_bytes", side_effect=PdfError("bad layout")
    )

    response = _post(api_client, "/convert/no-refs", math_act, output="pdf")

    assert response.status_code == 400
    assert "bad layout" in response.text


def test_validation(
    api_client: testclient.TestClient, generic_xml: bytes, generic_xsd: bytes
) -> None:
    """Validates against the uploaded schema and shows the result."""
    response = api_client.post(
        "/convert/no-refs",
        files=[
            (
                "file",
                ("doc.xml", generic_xml.replace(b"<p>Tekst</p>", b"<q/>")),
            ),
            ("schema_file", ("doc.xsd", generic_xsd)),
        ],
    )

    assert response.status_code == 200
    assert "wiersz" in response.text


@pytest.mark.parametrize(
    "path", ["/convert", "/convert/no-refs", "/convert/docx"]
)
def test_unusable_schema_upload(
    api_client: testclient.TestClient, path: str
) -> None:
    """Rejects a schema upload that holds no schema."""
    response = api_client.post(
        path,
        files=[
            ("file", ("akt.xml", b"<akt/>")),
            ("schema_file", ("s.zip", b"no zip")),
        ],
    )

    assert response.status_code == 400
    assert "Nie udało się wczytać schematu" in response.text


def test_form_returns_the_xml(
    api_client: testclient.TestClient, math_act: bytes, ref_service: MockType
) -> None:
    """Returns the XML itself, as a download, when asked for XML."""
    response = _post(api_client, "/convert/file", math_act, output="xml")

    assert response.content == math_act
    assert response.headers["content-disposition"].startswith("attachment;")
    ref_service.send.assert_not_called()


def test_form_with_references_and_validation(
    api_client: testclient.TestClient,
    generic_xml: bytes,
    generic_xsd: bytes,
    ref_service: MockType,
) -> None:
    """Looks up references and validates when both are ticked."""
    ref_service.send.return_value = generic_xml

    response = api_client.post(
        "/convert/file",
        files=[
            ("file", ("doc.xml", b"<doc/>")),
            ("schema_file", ("doc.xsd", generic_xsd)),
        ],
        data={"odeslania": "true", "walidacja": "true"},
    )

    assert response.status_code == 200
    assert ref_service.send.call_args.kwargs["filename"] == "doc.xml"


def test_form_converts_docx(
    api_client: testclient.TestClient, docx_service: MockType
) -> None:
    """Sends a DOCX to the converter and continues with its XML."""
    response = _post(
        api_client, "/convert/file", DOCX, filename="ustawa.docx", output="pdf"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert docx_service.send.call_args.kwargs["filename"] == "ustawa.docx"


@pytest.mark.parametrize(
    ("form", "message"),
    [
        ({"walidacja": "true"}, "Nie udało się wczytać schematu"),
        ({"odeslania": "true"}, "Wyszukiwanie odesłań nie powiodło się"),
    ],
)
def test_form_errors(
    api_client: testclient.TestClient,
    ref_service: MockType,
    form: dict[str, str],
    message: str,
) -> None:
    """Explains a failed option of the form."""
    ref_service.send.side_effect = UpstreamError("down")

    response = api_client.post(
        "/convert/file",
        files=[
            ("file", ("akt.xml", b"<akt/>")),
            ("schema_file", ("s.zip", b"no zip")),
        ],
        data=form,
    )

    assert response.status_code == 400
    assert message in response.text


def test_form_rejects_an_empty_file(api_client: testclient.TestClient) -> None:
    """Rejects an empty upload."""
    response = _post(api_client, "/convert/file", b"")

    assert response.status_code == 400
    assert "pusty" in response.text


def test_form_docx_failure(
    api_client: testclient.TestClient, docx_service: MockType
) -> None:
    """Explains a failed DOCX conversion."""
    docx_service.send.side_effect = UpstreamError("down")

    response = _post(api_client, "/convert/file", DOCX, filename="ustawa.docx")

    assert response.status_code == 400
    assert "Konwersja DOCX → XML nie powiodła się" in response.text


@pytest.mark.usefixtures("docx_service")
@pytest.mark.parametrize(("output", "status"), [("xml", 200), ("html", 200)])
def test_docx_endpoint(
    api_client: testclient.TestClient,
    ref_service: MockType,
    output: str,
    status: int,
) -> None:
    """Converts a DOCX with references looked up."""
    response = _post(
        api_client,
        "/convert/docx",
        DOCX,
        filename="ustawa.docx",
        output=output,
    )

    assert response.status_code == status
    assert ref_service.send.call_args.kwargs["filename"] == "ustawa.xml"


@pytest.mark.parametrize("failing", ["docx", "refs"])
def test_docx_endpoint_failures(
    api_client: testclient.TestClient,
    docx_service: MockType,
    ref_service: MockType,
    failing: str,
) -> None:
    """Explains which upstream step failed."""
    service = docx_service if failing == "docx" else ref_service
    service.send.side_effect = UpstreamError("down")

    response = _post(api_client, "/convert/docx", DOCX, filename="ustawa.docx")

    assert response.status_code == 400
