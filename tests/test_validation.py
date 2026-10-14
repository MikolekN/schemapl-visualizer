"""Test compiling XML Schemas uploaded with a request."""

import io
import zipfile

import pytest
from lxml import etree

from schemapl_visualizer.validation import (
    SchemaUploadError,
    ValidationStatus,
    load_validator_from_uploads,
)

PART_XSD = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:example" elementFormDefault="qualified">
  <xs:element name="p" type="xs:string"/>
</xs:schema>
"""

MAIN_XSD = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:e="urn:example" targetNamespace="urn:example"
           elementFormDefault="qualified">
  <xs:include schemaLocation="parts/part.xsd"/>
  <xs:element name="doc">
    <xs:complexType>
      <xs:sequence><xs:element ref="e:p" maxOccurs="unbounded"/></xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_single_schema(generic_xsd: bytes, generic_xml: bytes) -> None:
    """Compiles a single uploaded schema and validates against it."""
    validator = load_validator_from_uploads([("doc.xsd", generic_xsd)])

    result = validator.validate(etree.fromstring(generic_xml))

    assert result.status is ValidationStatus.VALID


def test_zipped_schema_starts_from_the_main_file(generic_xml: bytes) -> None:
    """Uses the schema no other one includes as the entry point."""
    archive = _zip(
        {"main.xsd": MAIN_XSD, "parts/part.xsd": PART_XSD, "readme.txt": b"x"}
    )

    validator = load_validator_from_uploads([("schema.zip", archive)])

    assert validator.path.name == "main.xsd"
    assert validator.validate(etree.fromstring(generic_xml)).is_valid


def test_invalid_document_lists_errors(generic_xsd: bytes) -> None:
    """Reports the line and column of each error."""
    validator = load_validator_from_uploads([("doc.xsd", generic_xsd)])

    result = validator.validate(
        etree.fromstring(b'<doc xmlns="urn:example"><q/></doc>')
    )

    assert result.status is ValidationStatus.INVALID
    assert result.errors
    assert result.errors[0].startswith("wiersz 1")


def test_zip_slip_entries_are_skipped(generic_xsd: bytes) -> None:
    """Ignores archive entries that point outside the upload folder."""
    archive = _zip({"../evil.xsd": generic_xsd, "doc.xsd": generic_xsd})

    validator = load_validator_from_uploads([("schema.zip", archive)])

    assert validator.path.name == "doc.xsd"


def test_upload_without_xsd() -> None:
    """Rejects uploads that contain no schema."""
    with pytest.raises(SchemaUploadError, match=r"\.xsd"):
        load_validator_from_uploads([("notes.txt", b"x")])


def test_broken_archive() -> None:
    """Rejects an archive that cannot be read."""
    with pytest.raises(SchemaUploadError, match=r"\.zip"):
        load_validator_from_uploads([("schema.zip", b"not a zip")])


def test_schema_that_does_not_compile() -> None:
    """Returns a validator that reports why the schema is unusable."""
    validator = load_validator_from_uploads([("bad.xsd", b"<xs:schema/>")])

    assert not validator.compiled
    assert validator.load_error
