"""Secure XML parsing.

A fresh parser is built per call: libxml2 parsers are not safe to share
across threads, and the web service may parse concurrently.
"""

from __future__ import annotations

from lxml import etree


def build_secure_parser() -> etree.XMLParser:
    """A parser that leaves entities unresolved, for large trees."""
    return etree.XMLParser(
        resolve_entities=False,
        huge_tree=True,
    )


def parse_xml(data: bytes) -> etree._Element:
    """The root element of ``data``, parsed with a fresh parser."""
    return etree.fromstring(data, build_secure_parser())
