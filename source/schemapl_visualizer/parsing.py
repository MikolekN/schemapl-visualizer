"""Secure XML parsing.

A fresh parser is built per call: libxml2 parsers are not safe to share
across threads, and the web service may parse concurrently.

libxml2's own limits stay on (256 levels, 10 MB of text in one node).
Below them, a document nested deeper than MAX_DEPTH levels is refused:
the converters follow the tree recursively, and real acts go about 25
levels deep.
"""

from __future__ import annotations

from lxml import etree

MAX_DEPTH = 100


class DocumentTooDeepError(ValueError):
    """The document is nested too deeply to convert."""


def build_secure_parser() -> etree.XMLParser:
    """A parser that leaves entities unresolved."""
    return etree.XMLParser(resolve_entities=False)


def parse_xml(data: bytes) -> etree._Element:
    """The root element of ``data``, parsed with a fresh parser.

    A document nested deeper than MAX_DEPTH levels raises
    DocumentTooDeepError.
    """
    root = etree.fromstring(data, build_secure_parser())
    if _depth(root) > MAX_DEPTH:
        message = f"The document is nested deeper than {MAX_DEPTH} levels."
        raise DocumentTooDeepError(message)
    return root


def _depth(root: etree._Element) -> int:
    """How many levels of elements the tree has, the root being one."""
    depth = deepest = 0
    for event, _ in etree.iterwalk(root, events=("start", "end")):
        depth += 1 if event == "start" else -1
        deepest = max(deepest, depth)
    return deepest
