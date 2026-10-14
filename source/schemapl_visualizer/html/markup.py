"""
Tiny helpers for building HTML strings safely.

Everything returns a ``markupsafe.Markup`` and any plain text from the
document is escaped first — so document content can never accidentally
break out of its tags or inject markup.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from markupsafe import Markup, escape


def escape_text(value: str | None) -> Markup:
    return escape(value if value is not None else "")


def join(parts: Iterable[Markup]) -> Markup:
    return Markup("").join(parts)


def html_tag(
    name: str,
    inner: Markup | str = "",
    *,
    css_class: str | None = None,
    attributes: Mapping[str, str | None] | None = None,
) -> Markup:
    """Build ``<name class="...">inner</name>``."""
    opening = "<" + name
    if css_class:
        opening += ' class="' + str(escape(css_class)) + '"'
    if attributes:
        for key, value in attributes.items():
            if value is None:
                continue
            opening += " " + key + '="' + str(escape(value)) + '"'
    return Markup(opening + ">") + Markup(inner) + Markup("</" + name + ">")


def void_tag(
    name: str,
    *,
    css_class: str | None = None,
    attributes: Mapping[str, str | None] | None = None,
) -> Markup:
    """Build a tag with no closing tag, e.g. ``<img ...>`` or ``<hr>``."""
    opening = "<" + name
    if css_class:
        opening += ' class="' + str(escape(css_class)) + '"'
    if attributes:
        for key, value in attributes.items():
            if value is None:
                continue
            opening += " " + key + '="' + str(escape(value)) + '"'
    return Markup(opening + ">")
