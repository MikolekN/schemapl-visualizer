"""Generic rendering engine — schema-independent.

The engine walks the XML tree, asks the active :class:`Profile` to
render each element, and falls back to a plain labelled "node" view when
the profile does not recognise it. It knows nothing about schemaPL (or
any other vocabulary): element names, markers and namespaces all live in
a profile (see ``profiles/``). To support a new schema you add a
profile, not engine code.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from lxml import etree
from markupsafe import Markup

from ..namespaces import (
    attribute_label,
    display_label,
    element_name,
    is_element,
)
from .markup import escape_text, html_tag, join


class Profile(Protocol):
    """What the engine needs from a schema profile."""

    display_prefixes: dict[str, str]

    def dispatch(
        self, element: etree._Element, state: RenderState, inline: bool, /
    ) -> Markup | None:
        """Render the element, or ``None`` for the generic fallback."""


class GenericProfile:
    """Fallback profile: every element gets the generic view."""

    def __init__(self) -> None:
        """Start without display prefixes of its own."""
        self.display_prefixes: dict[str, str] = {}

    def dispatch(
        self, _element: etree._Element, _state: RenderState, _inline: bool
    ) -> Markup | None:
        """Render nothing specially: ``None`` for every element."""
        return None


GENERIC = GenericProfile()


@dataclass(frozen=True)
class Footnote:
    """A footnote collected while rendering, shown at the end."""

    key: str
    symbol: str
    content: Markup
    # False: the note has no call site in the text to link back to
    placed: bool = True


@dataclass(frozen=True)
class TocEntry:
    """One link of the table of contents."""

    anchor: str
    marker: str
    title: str
    kind: str
    depth: int
    preview: str = ""


@dataclass
class RenderState:
    """What rendering one document collects and keeps track of."""

    footnotes: list[Footnote] = field(default_factory=list)
    metadata_html: Markup = field(default_factory=Markup)
    title: str = ""
    uses_math: bool = False
    toc: list[TocEntry] = field(default_factory=list)
    used_ids: set[str] = field(default_factory=set)
    anchor_count: int = 0
    toc_depth: int = 0
    anchor_suppression: int = 0
    profile: Profile | None = None
    prefixes: dict[str, str] = field(default_factory=dict)
    # per-document scratch space for the profile
    profile_data: dict[str, object] = field(default_factory=dict)


def _prefixes_from_document(root: etree._Element) -> dict[str, str]:
    """Namespace URL -> prefix, from the document's own declarations."""
    mapping: dict[str, str] = {}
    for prefix, uri in (root.nsmap or {}).items():
        if uri and uri not in mapping:
            mapping[uri] = prefix or ""
    return mapping


def render_document_body(root: etree._Element, state: RenderState) -> Markup:
    """Render the whole document body, then the collected footnotes."""
    if state.profile is None:
        state.profile = GENERIC
    state.prefixes = {
        **_prefixes_from_document(root),
        **getattr(state.profile, "display_prefixes", {}),
    }
    body = render_element(root, state)
    return body + render_footnotes_section(state.footnotes)


def render_element(
    element: etree._Element, state: RenderState, *, inline: bool = False
) -> Markup:
    """Dispatch one element to the active profile or the fallback."""
    if not is_element(element):
        return Markup("")  # skip comments and processing instructions
    profile = state.profile or GENERIC
    result = profile.dispatch(element, state, inline)
    if result is None:
        return render_unknown_element(element, state, inline)
    return result


def render_children(
    element: etree._Element, state: RenderState, *, inline: bool
) -> Markup:
    """Render an element's text and child elements, in document order.

    This is what keeps "running text with inline references" reading
    correctly: lxml stores text before the first child in
    ``element.text`` and text after each child in ``child.tail``.
    """
    parts: list[Markup] = []
    if element.text and (inline or element.text.strip()):
        parts.append(_text_piece(element.text, inline))
    for child in element:
        if is_element(child):
            parts.append(render_element(child, state, inline=inline))
        if child.tail and (inline or child.tail.strip()):
            parts.append(_text_piece(child.tail, inline))
    return join(parts)


def render_child_elements(
    element: etree._Element, state: RenderState, *, skip: Iterable[str] = ()
) -> Markup:
    """Render only the child elements, as blocks.

    Children named in ``skip`` are left out.
    """
    skip_names = set(skip)
    return join(
        render_element(child, state)
        for child in element
        if is_element(child) and element_name(child) not in skip_names
    )


def _text_piece(value: str, inline: bool) -> Markup:
    """A run of text: bare (escaped) inline, in a span as a block."""
    if inline:
        return escape_text(value)
    return html_tag("span", escape_text(value), css_class="text")


_ID_SAFE = re.compile(r"[A-Za-z][\w.\-/\[\]]*")


def _register_anchor(
    element: etree._Element, state: RenderState, prefix: str
) -> str | None:
    """A unique HTML id for a unit: its eId if usable, else a new one.

    Returns ``None`` inside quoted/footnote content — those eIds belong
    to the quoted act and would collide with the host document's
    anchors.
    """
    if state.anchor_suppression:
        return None
    eid = (element.get("eId") or "").strip()
    anchor = (
        eid
        if eid and eid not in state.used_ids and _ID_SAFE.fullmatch(eid)
        else ""
    )
    if not anchor:
        state.anchor_count += 1
        anchor = f"{prefix}-{state.anchor_count}"
    state.used_ids.add(anchor)
    return anchor


def render_toc(entries: list[TocEntry]) -> Markup:
    """The table of contents for the left panel.

    Empty markup when there is nothing to list.
    """
    links = []
    for entry in entries:
        depth = min(entry.depth, 6)
        marker = html_tag(
            "span", escape_text(entry.marker), css_class="toc__marker"
        )
        if entry.title:
            title = html_tag(
                "span", escape_text(entry.title), css_class="toc__title"
            )
        elif entry.preview:
            title = html_tag(
                "span", escape_text(entry.preview), css_class="toc__preview"
            )
        else:
            title = Markup("")
        links.append(
            html_tag(
                "a",
                marker + title,
                css_class=f"toc__link toc__link--{entry.kind} toc-d{depth}",
                attributes={"href": f"#{entry.anchor}"},
            )
        )
    return join(links)


def _has_loose_text(element: etree._Element) -> bool:
    """True when text sits next to child elements (mixed content)."""
    if element.text and element.text.strip():
        return True
    return any(child.tail and child.tail.strip() for child in element)


def _has_child_elements(element: etree._Element) -> bool:
    return any(is_element(child) for child in element)


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() not in (
        "",
        "0",
        "false",
    )


def render_footnotes_section(footnotes: list[Footnote]) -> Markup:
    """The notes section appended at the very end of the document."""
    if not footnotes:
        return Markup("")
    notes = []
    for note in footnotes:
        symbol = html_tag(
            "sup", escape_text(note.symbol), css_class="footnote__symbol"
        )
        body = html_tag("div", note.content, css_class="footnote__body")
        back = Markup("")
        if note.placed:
            back = html_tag(
                "a",
                Markup("↩"),
                css_class="footnote__back",
                attributes={"href": f"#fnref-{note.key}", "title": "Powrót"},
            )
        notes.append(
            html_tag(
                "div",
                symbol + body + back,
                css_class="footnote",
                attributes={"id": f"fn-{note.key}"},
            )
        )
    return html_tag(
        "section",
        Markup("<hr>") + join(notes),
        css_class="footnotes",
        attributes={"aria-label": "Przypisy"},
    )


def render_unknown_element(
    element: etree._Element, state: RenderState, inline: bool
) -> Markup:
    """The generic view of an element: label, attributes, content."""
    name = element_name(element)
    label = _label(display_label(element, state.prefixes))
    chips = _attribute_chips(element, state.prefixes)

    if inline:
        body = render_children(element, state, inline=True)
        return html_tag(
            "span", label + chips + body, css_class=f"inline node--{name}"
        )

    if not _has_child_elements(element):
        return _render_leaf(element, name, label, chips)

    if _has_loose_text(element):
        body = render_children(element, state, inline=True)
        head = html_tag("div", label + chips, css_class="node__head")
        body_div = html_tag("div", body, css_class="node__body rich")
        return html_tag("div", head + body_div, css_class=f"node node--{name}")

    body = render_children(element, state, inline=False)
    head = html_tag("div", label + chips, css_class="node__head")
    body_div = html_tag("div", body, css_class="node__body")
    return html_tag(
        "div", head + body_div, css_class=f"node collapsible node--{name}"
    )


def _label(text: str) -> Markup:
    return html_tag("span", escape_text(text), css_class="node__label")


def _render_leaf(
    element: etree._Element, name: str, label: Markup, chips: Markup
) -> Markup:
    text = element.text
    if text and text.strip():
        body = html_tag("span", escape_text(text), css_class="text")
    else:
        # empty-set glyph
        body = html_tag("span", Markup("&#8709;"), css_class="empty")
    return html_tag(
        "div", label + chips + body, css_class=f"node leaf node--{name}"
    )


def _attribute_chips(
    element: etree._Element, prefixes: dict[str, str]
) -> Markup:
    chips = []
    for key, value in element.attrib.items():
        name = html_tag("b", escape_text(attribute_label(key, prefixes)))
        chips.append(
            html_tag(
                "span",
                name + Markup("=") + escape_text(value),
                css_class="attr",
            )
        )
    if not chips:
        return Markup("")
    return html_tag("span", join(chips), css_class="attrs")
