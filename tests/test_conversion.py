"""Test conversion of XML documents into HTML and PDF."""

from pathlib import Path

import pytest
from lxml import etree

from schemapl_visualizer import (
    ConversionResult,
    SchemaValidator,
    UnsupportedDocument,
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
    with pytest.raises(UnsupportedDocument):
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

    assert "root:" not in result.text


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
