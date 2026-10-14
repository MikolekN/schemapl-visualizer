"""Test conversion of XML documents into HTML and PDF."""

from pathlib import Path

import pytest
from lxml import etree
from pytest_mock import MockerFixture

from schemapl_visualizer import (
    MAX_DEPTH,
    ConversionResult,
    DocumentTooDeepError,
    SchemaValidator,
    UnsupportedDocumentError,
    available_formats,
    convert_bytes,
    convert_file,
    load_validator,
)

# Sample schemaPL acts: formulas, an amending act, a consolidated text,
# a bill, its amendment and a judgment.
SAMPLE_ACTS = sorted((Path(__file__).resolve().parent / "data").glob("*.xml"))


def test_available_formats() -> None:
    """Lists every output format."""
    assert available_formats() == ["html", "pdf", "pdf-accessible"]


@pytest.mark.parametrize("act", SAMPLE_ACTS, ids=lambda path: path.stem)
def test_sample_act_to_html(act: Path) -> None:
    """Renders each sample act as a complete HTML page."""
    result = convert_file(act)

    assert result.media_type == "text/html; charset=utf-8"
    assert result.file_extension == "html"
    assert result.text.startswith("<!DOCTYPE html>")
    assert act.name in result.text


@pytest.mark.parametrize("act", SAMPLE_ACTS, ids=lambda path: path.stem)
@pytest.mark.parametrize(
    ("output_format", "extension"),
    [("pdf", "pdf"), ("pdf-accessible", "accessible.pdf")],
)
def test_sample_act_to_pdf(
    act: Path, output_format: str, extension: str
) -> None:
    """Typesets each sample act in both PDF layouts."""
    result = convert_file(act, output_format=output_format)

    assert result.media_type == "application/pdf"
    assert result.file_extension == extension
    assert result.content.startswith(b"%PDF-")


def test_accessible_pdf_is_tagged(math_act: bytes) -> None:
    """Marks the accessible PDF as PDF/UA."""
    result = convert_bytes(
        math_act, source_name="akt.xml", output_format="pdf-accessible"
    )

    assert b"pdfuaid" in result.content


def test_math_is_rendered_for_mathjax(
    math_act: bytes, generic_xml: bytes
) -> None:
    """Loads MathJax only for documents with formulas."""
    with_math = convert_bytes(math_act, source_name="akt.xml")
    without_math = convert_bytes(generic_xml, source_name="doc.xml")

    assert "mathjax" in with_math.text
    assert "mathjax" not in without_math.text


def test_unknown_document_falls_back_to_generic_html(
    generic_xml: bytes,
) -> None:
    """Renders XML of an unknown vocabulary with the generic profile."""
    result = convert_bytes(generic_xml, source_name="doc.xml")

    assert "Tekst" in result.text


def test_unknown_document_has_no_pdf(generic_xml: bytes) -> None:
    """Refuses PDF output for documents no PDF profile handles."""
    with pytest.raises(UnsupportedDocumentError):
        convert_bytes(generic_xml, source_name="doc.xml", output_format="pdf")


def test_unknown_format_is_rejected(generic_xml: bytes) -> None:
    """Names the available formats when the requested one is unknown."""
    with pytest.raises(ValueError, match="Available: html"):
        convert_bytes(generic_xml, source_name="doc.xml", output_format="docx")


def test_malformed_xml_is_rejected() -> None:
    """Raises the parser's error for malformed XML."""
    with pytest.raises(etree.XMLSyntaxError):
        convert_bytes(b"<doc>", source_name="doc.xml")


def test_entities_are_not_resolved() -> None:
    """Leaves external entities unresolved."""
    document = (
        b'<?xml version="1.0"?><!DOCTYPE doc [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b'<doc xmlns="urn:example"><p>&e;</p></doc>'
    )

    result = convert_bytes(document, source_name="doc.xml")

    assert "root:x:0:0" not in result.text


def _nested(depth: int) -> bytes:
    """A document ``depth`` levels deep, its root included."""
    inner = "<x>" * (depth - 1) + "t" + "</x>" * (depth - 1)
    return f'<doc xmlns="urn:example">{inner}</doc>'.encode()


def test_nesting_up_to_the_limit_is_converted() -> None:
    """Converts a document exactly MAX_DEPTH levels deep."""
    result = convert_bytes(_nested(MAX_DEPTH), source_name="doc.xml")

    assert result.text.startswith("<!DOCTYPE html>")


def test_deeper_nesting_is_refused() -> None:
    """Refuses a document nested deeper than MAX_DEPTH levels."""
    with pytest.raises(DocumentTooDeepError, match=str(MAX_DEPTH)):
        convert_bytes(_nested(MAX_DEPTH + 1), source_name="doc.xml")


def test_parser_keeps_its_depth_limit() -> None:
    """Leaves libxml2's own limit on nesting in place."""
    with pytest.raises(etree.XMLSyntaxError, match="depth"):
        convert_bytes(_nested(300), source_name="doc.xml")


def test_runaway_recursion_is_refused(
    mocker: MockerFixture, generic_xml: bytes
) -> None:
    """Reports nesting the renderer cannot follow as too deep."""
    mocker.patch.dict(
        "schemapl_visualizer.conversion.OUTPUT_FORMATS",
        {"html": mocker.Mock(side_effect=RecursionError)},
    )

    with pytest.raises(DocumentTooDeepError):
        convert_bytes(generic_xml, source_name="doc.xml")


def test_validation_result_is_shown(
    tmp_path: Path, generic_xml: bytes, generic_xsd: bytes
) -> None:
    """Shows the schema validation result in the HTML page."""
    schema = tmp_path / "doc.xsd"
    schema.write_bytes(generic_xsd)
    validator = load_validator(schema)
    invalid = generic_xml.replace(b"<p>Tekst</p>", b"<q/>")

    valid_page = convert_bytes(
        generic_xml, source_name="doc.xml", validator=validator
    )
    invalid_page = convert_bytes(
        invalid, source_name="doc.xml", validator=validator
    )

    assert isinstance(valid_page, ConversionResult)
    assert "wiersz" not in valid_page.text
    assert "wiersz" in invalid_page.text


def test_missing_schema_is_reported(
    tmp_path: Path, generic_xml: bytes
) -> None:
    """Reports a schema that cannot be loaded instead of failing."""
    validator = load_validator(tmp_path / "missing.xsd")

    assert isinstance(validator, SchemaValidator)
    assert not validator.compiled
    assert validator.load_error
    assert validator.validate(etree.fromstring(generic_xml)).schema_error


def test_no_schema_means_no_validator() -> None:
    """Skips validation when no schema is given."""
    assert load_validator(None) is None


def test_footnote_opening_with_a_table(data_dir: Path) -> None:
    """Typesets a footnote whose first block is a table."""
    act = data_dir / "DU20261261_obw_tj.xml"
    root = etree.parse(str(act)).getroot()
    namespace = etree.QName(root).namespace
    note = root.find(f".//{{{namespace}}}odnosnik")
    assert note is not None
    table = etree.Element(f"{{{namespace}}}tabela")
    row = etree.SubElement(table, f"{{{namespace}}}tr")
    etree.SubElement(row, f"{{{namespace}}}td").text = "x"
    note.insert(0, table)

    result = convert_bytes(
        etree.tostring(root), source_name="akt.xml", output_format="pdf"
    )

    assert result.content.startswith(b"%PDF-")


def test_page_is_named_after_the_act(data_dir: Path) -> None:
    """Names the page after the act's title from its metadata."""
    result = convert_file(data_dir / "wyrok_TK.xml")

    assert (
        "<title>Wyrok Trybunału Konstytucyjnego z dnia 15 kwietnia 2021 r."
        in result.text
    )
    assert "wyrok_TK.xml" in result.text  # the file name stays visible


def test_bill_is_named_after_its_heading(data_dir: Path) -> None:
    """Names a bill without a metadata title after its own heading."""
    result = convert_file(data_dir / "projekt01.xml")

    assert "<title>O odbudowie polskiej kolei" in result.text


def test_untitled_articles_show_their_first_words(data_dir: Path) -> None:
    """Gives untitled articles in the outline their opening words."""
    result = convert_file(data_dir / "projekt01.xml")

    assert '<span class="toc__preview">W ustawie z dnia' in result.text


@pytest.mark.parametrize(
    ("act", "expected"),
    [
        (
            "DU20261261_obw_tj.xml",
            [
                '<div class="meta-card__address">Dz.U. 2026 poz. 1261</div>',
                '<span class="pill pill--ok">obowiązuje</span>',
                "isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260001261",
            ],
        ),
        (
            "projekt01.xml",
            [
                '<div class="meta-card__type">projekt ustawy</div>',
                '<div class="meta-card__address">Druk nr 2887</div>',
            ],
        ),
    ],
)
def test_document_panel_opens_with_a_summary(
    data_dir: Path, act: str, expected: list[str]
) -> None:
    """Opens the document panel with a summary card of the act."""
    result = convert_file(data_dir / act)

    for fragment in expected:
        assert fragment in result.text


def test_no_validation_banner_without_validation(generic_xml: bytes) -> None:
    """Shows no validation note when no validation was asked for."""
    result = convert_bytes(generic_xml, source_name="doc.xml")

    page_body = result.text.split("<body>", 1)[1].split("<script>", 1)[0]
    assert "banner" not in page_body


@pytest.mark.usefixtures("fixed_now")
def test_page_shows_when_it_was_generated(generic_xml: bytes) -> None:
    """Shows the time of the conversion in the page's metadata."""
    result = convert_bytes(generic_xml, source_name="doc.xml")

    assert "2026-01-01 12:00" in result.text
