"""Helpers for reading an element's name and building a display label.

This module is schema-independent: the display prefixes are supplied by
the caller (derived from the document and the active profile), not
hardcoded here.
"""

from __future__ import annotations

from lxml import etree


def is_element(node: etree._Element) -> bool:
    """True for elements, False for comments and instructions."""
    return isinstance(node.tag, str)


def element_name(element: etree._Element) -> str:
    """The element's local tag name, e.g. ``"artykul"``."""
    return etree.QName(element).localname


def element_namespace(element: etree._Element) -> str | None:
    """The element's namespace URL, or ``None``."""
    return etree.QName(element).namespace


def has_name(element: etree._Element, namespace: str, name: str) -> bool:
    """True if the element is exactly ``<namespace:name>``."""
    qualified = etree.QName(element)
    return qualified.namespace == namespace and qualified.localname == name


def display_label(element: etree._Element, prefixes: dict[str, str]) -> str:
    """A short label for the fallback view, e.g. ``"now:foo"``."""
    qualified = etree.QName(element)
    prefix = prefixes.get(qualified.namespace or "")
    return f"{prefix}:{qualified.localname}" if prefix else qualified.localname


def attribute_label(key: str, prefixes: dict[str, str]) -> str:
    """Turn lxml's ``"{ns}name"`` attribute key into a label."""
    if key.startswith("{"):
        namespace, _, name = key[1:].partition("}")
        prefix = prefixes.get(namespace)
        return f"{prefix}:{name}" if prefix else name
    return key
