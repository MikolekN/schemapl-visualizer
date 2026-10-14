"""Provide sample documents and an HTTP client for the tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import testclient

DATA_DIR = Path(__file__).resolve().parent / "data"


@pytest.fixture
def math_act() -> bytes:
    """Provides the sample act with MathML formulas.

    Returns:
        The act's XML.
    """
    return (DATA_DIR / "przyklady_kancelaria_sejmu.xml").read_bytes()


@pytest.fixture
def generic_xml() -> bytes:
    """Provides a document in a vocabulary no profile knows.

    Returns:
        The document's XML.
    """
    return b'<?xml version="1.0"?><doc xmlns="urn:example"><p>Tekst</p></doc>'


@pytest.fixture
def generic_xsd() -> bytes:
    """Provides an XML Schema the generic document satisfies.

    Returns:
        The schema's XSD.
    """
    return b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="urn:example" elementFormDefault="qualified">
  <xs:element name="doc">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="p" type="xs:string" maxOccurs="unbounded"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


@pytest.fixture(name="api_client")
def api_client_fixture() -> Iterator[testclient.TestClient]:
    """Provides a client for the FastAPI application.

    Yields:
        A client whose application lifecycle is active for the test.
    """
    import main

    with testclient.TestClient(main.app) as client:
        yield client
