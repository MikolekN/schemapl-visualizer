"""Tiny helpers for building HTML strings safely.

Everything returns a ``markupsafe.Markup`` and any plain text from the
document is escaped first — so document content can never accidentally
break out of its tags or inject markup.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from markupsafe import Markup, escape


def escape_text(value: str | None) -> Markup:
    """Escape document text; ``None`` becomes empty markup."""
    return escape(value if value is not None else "")


def join(parts: Iterable[Markup]) -> Markup:
    """Concatenate markup without escaping it again."""
    return Markup("").join(parts)


def _start_tag(
    name: str,
    css_class: str | None,
    attributes: Mapping[str, str | None] | None,
) -> Markup:
    """The opening tag, with every attribute value escaped."""
    tag = Markup("<{}").format(name)
    if css_class:
        tag += Markup(' class="{}"').format(css_class)
    for key, value in (attributes or {}).items():
        if value is not None:
            tag += Markup(' {}="{}"').format(key, value)
    return tag + Markup(">")


def html_tag(
    name: str,
    inner: Markup | str = "",
    *,
    css_class: str | None = None,
    attributes: Mapping[str, str | None] | None = None,
) -> Markup:
    """Build ``<name class="...">inner</name>``.

    ``inner`` is markup already: callers escape any document text in it.
    """
    start = _start_tag(name, css_class, attributes)
    body = Markup(inner)  # noqa: S704 - inner is markup by contract
    return start + body + Markup("</{}>").format(name)


def void_tag(
    name: str,
    *,
    css_class: str | None = None,
    attributes: Mapping[str, str | None] | None = None,
) -> Markup:
    """Build a tag with no closing tag, e.g. ``<img ...>``."""
    return _start_tag(name, css_class, attributes)
