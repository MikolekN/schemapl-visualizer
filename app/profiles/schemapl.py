"""
schemaPL profile — the schema-specific knowledge for Polish legal acts.

Everything here is specific to the schemaPL vocabulary: the namespace URLs, the
element names, and how each element is turned into HTML. The engine (engine.py)
knows none of it; it calls :func:`dispatch`, which returns ``None`` for anything
this profile does not handle so the engine can fall back to a generic view.

To support another schema, add a sibling module shaped like this one and register
its profile in ``app/profiles/__init__.py`` — the engine does not change.
"""

from __future__ import annotations

import re

from lxml import etree
from markupsafe import Markup, escape

from ..engine import (
    Footnote,
    RenderState,
    TocEntry,
    render_child_elements,
    render_children,
    render_element,
    render_unknown_element,
    _has_child_elements,
    _is_truthy,
    _register_anchor,
)
from ..html import escape_text, html_tag, join, void_tag
from .schemapl_common import (
    ACT_TYPE_LABELS,
    AMENDMENT_NS,
    COMMENTS_NS,
    DISPLAY_PREFIXES,
    FOOTNOTE_NAMES,
    GUID_NS,
    HEADING_WORDS,
    InternalLinks,
    MATHML,
    SCHEMAPL,
    SECTION_UNITS,
    SVG,
    TYPOGRAPHY_HINTS,
    TYPOGRAPHY_NS,
    UNIT_MARKERS,
    XMLDSIG,
    amendment_label,
    child_named,
    field_value,
    format_date,
    format_eid,
    is_annotation,
    number_of,
    person_name,
    plain_text,
    quote_marks,
    section_outline,
    sibling_element,
    superscript_parts,
    superscripts_text,
)
from ..namespaces import (
    attribute_label,
    display_label,
    element_name,
    element_namespace,
    has_name,
    is_element,
)


ARTICLE_TOC_NAMES = {
    "artykul",
    "artykul-kodeksu",
    "artykul-tj",
    "artykul-kodeksu-tj",
    "nie-ztp-artykul",
    "paragraf",
    "paragraf-tj",
    "nie-ztp-paragraf-rozporzadzenia",
}

TRANSPARENT_WRAPPERS = {
    "akt-prawny",
    "ustawa",
    "kodeks",
    "rozporzadzenie",
    "zarzadzenie",
    "uchwala",
    "inny-akt-prawny",
    "obwieszczenie",
    "orzeczenieTK",
    "projekt-ustawy",
    "projekt-kodeksu",
    "autopoprawka",
    "ksiega-n",
    "czesc-n",
    "tytul-n",
    "tytul-n-jednostka",
    "dzial-n",
    "oddzial-n",
    "rozdzial-n",
    "ustep-n",
    "paragraf-kodeksu-n",
    "nie-ztp-ustep-n",
    "nie-ztp-paragraf-kodeksu-n",
}

CONTAINER_BLOCKS = {
    "preambula": "preambula",
    "uzasadnienie": "uzasadnienie",
    "sekcja-uzasadnienia": "sekcja-uzasadnienia",
    "zalacznik": "zalacznik",
    "zalacznik-tekstowy": "zalacznik",
    "segment-zalacznika": "segment-zalacznika",
    "czesc-zatytulowana": "czesc-zatytulowana",
    "upowaznienie-do-reprezentowania": "upowaznienie",
    "odnosnik-cyt": "odnosnik-cyt",
    "sklad-sedziowski": "sklad-sedziowski",
    "przedmiot-sprawy": "przedmiot-sprawy",
    "zarzuty": "zarzuty",
    "tenor-orzeczenia": "tenor-orzeczenia",
    "postanowienie-dodatkowe": "postanowienie-dodatkowe",
    "zdanie-odrebne": "zdanie-odrebne",
    "podpisy": "podpisy-blok",
}

TEXT_BLOCKS = {
    "podstawa-prawna": "podstawa-prawna",
    "slubowanie": "slubowanie",
    "sankcja-karna": "sankcja-karna",
    "fragment": "fragment",
    "fragment-odnosnik": "fragment",
    "uwagi": "uwagi",
    "podstawa-inicjowania": "podstawa-inicjowania",
    "wynik-narady": "wynik-narady",
    "poswiadczenie": "poswiadczenie",
    "tresc": "tresc",
    "tytul-tabeli": "tytul-tabeli",
    "odstep-tabeli": "odstep-tabeli",
    "uchylenie-OTJ": "uchylenie-OTJ",
    "tytul-sekcji": "tytul-sekcji",
    "tytul-uzasadnienia": "tytul-uzasadnienia",
    "tytul-zalacznika": "tytul-zalacznika",
    "zalacznik-do": "zalacznik-do",
    "organ-wydajacy": "podpis",
    "organ-podpisujacy": "podpis",
    "tekst-w-porozumieniu": "podpis",
    "organ-w-porozumieniu": "podpis",
    "podpisujacy": "podpis podpisujacy",
    "protokolant": "protokolant",
    "opis-tabeli": "opis-tabeli",
    "opis-grafiki": "opis-grafiki",
    "wprowadzenie-do-opisu": "wzor-mat__wprowadzenie",
    "winieta": "winieta",
    "kadencja": "kadencja",
    "miejsce-i-data": "miejsce-i-data",
    "adresat-pisma-tytul-i-osoba": "adresat-pisma",
    "adresat-pisma-stanowisko": "adresat-pisma",
    "kontynuacja-preambuly": "kontynuacja-preambuly",
    "tytul-kolumny": "cell-header",
    "tekst-centr": "cell-center",
    "liczba": "cell-number",
    "tekst-zwykly": "cell-text",
    "tekst-1": "cell-indent-1",
    "tekst-2": "cell-indent-2",
    "tekst-3": "cell-indent-3",
    "wyliczenie-1": "cell-list-1",
    "wyliczenie-2": "cell-list-2",
    "wyliczenie-3": "cell-list-3",
    "wyliczenie-4": "cell-list-4",
}

INLINE_FORMAT_TAGS = {"b": "b", "i": "i", "sup": "sup", "sub": "sub"}

INLINE_SPANS = {
    "wersaliki": "wersaliki",
    "rozstrzelone": "rozstrzelone",
    "petit": "petit",
    "skrot": "skrot",
    "odeslanie-tytul": "odeslanie-tytul",
    "wynik-inline": "wynik-inline",
    "podmiot-inicjujacy": "podmiot-inicjujacy",
    "tryb-orzekania": "tryb-orzekania",
    "kwestionowany-przepis": "kwestionowany-przepis",
    "wzorzec-kontroli": "wzorzec-kontroli",
}

REFERENCE_NAMES = {"ref", "rref", "mref"}

BLOCK_QUOTE_NAMES = {"cytat-strukt", "cytat-blok", "tresc-strukt"}

FLOWING_TEXT_NAMES = {"zdanie", "tekst"}

FORMULA_PARTS = {"wzor", "opis", "symbol-txt", "symbol-mat", "objasnienie"}

DOCUMENT_HEADER_NAMES = {
    "rodzaj-aktu",
    "autor-aktu",
    "data",
    "daty",
    "sygnatura",
    "oznaczenie",
    "tytul-ustawy",
    "tytul-kodeksu",
}

DOCUMENT_HEADER_CLASS = {
    "rodzaj-aktu": "doc-type",
    "autor-aktu": "doc-author",
    "data": "doc-date",
    "daty": "doc-date",
    "sygnatura": "doc-signature",
    "oznaczenie": "doc-designation",
    "tytul": "doc-title",
    "tytul-ustawy": "doc-title",
    "tytul-kodeksu": "doc-title",
}

ACT_TITLE_PARENTS = {
    "ustawa",
    "kodeks",
    "rozporzadzenie",
    "zarzadzenie",
    "uchwala",
    "inny-akt-prawny",
    "obwieszczenie",
    "orzeczenieTK",
    "projekt-ustawy",
    "projekt-kodeksu",
    "autopoprawka",
    "akt-prawny",
}

def dispatch(element: etree._Element, state: RenderState, inline: bool) -> Markup | None:
    if not is_element(element):
        return Markup("")  # skip comments and processing instructions

    namespace = element_namespace(element)
    name = element_name(element)

    if namespace == AMENDMENT_NS:  # now:
        return render_amendment_marker(element, state)
    if namespace == MATHML and name == "math":    # mml:
        return render_math(element, state, inline)
    if namespace == XMLDSIG:  # e-podpisy: the cryptographic signature block
        return render_xmldsig(element, state)
    if namespace == TYPOGRAPHY_NS and name in TYPOGRAPHY_HINTS:  # tpg:
        return Markup("")  # akapit / typografia: print-formatting hints only
    if namespace == COMMENTS_NS:  # kmn:
        return render_editorial_comment(element, state, inline)
    if namespace != SCHEMAPL:  # anything unexpected
        return None

    if name == "metadane":
        return collect_metadata(element, state)
    if name in INLINE_FORMAT_TAGS:
        return render_inline_format(element, state)  # b / i / sup / sub
    if name in INLINE_SPANS:
        return render_inline_span(element, state)  # wersaliki / petit / skrot / ...
    if name == "h":
        return render_hyperlink(element)
    if name == "pole":
        return render_field(element, state)
    if name == "metryczka":
        return render_publication_reference(element)
    if name == "osoba":
        return render_person(element, inline)
    if name in REFERENCE_NAMES:
        return render_reference(element, state)  # ref / rref / mref
    if name == "definicja-legalna":
        return render_defined_term(element, state)
    if name == "cytat-w-tekscie":
        return render_inline_quotation(element, state)
    if name in BLOCK_QUOTE_NAMES:
        return render_block_quotation(element, state)
    if name in FOOTNOTE_NAMES:
        return render_footnote(element, state)
    if name == "p":
        return render_paragraph(element, state)
    if name in FLOWING_TEXT_NAMES:
        return render_flowing_text(element, state)  # zdanie / tekst
    if name == "specjalny":
        return render_special(element, state, inline)
    if name == "sedzia":
        return render_judge(element, state)
    if name == "tytul":
        return render_title(element, state)  # act title / systematization unit / article title
    if name in DOCUMENT_HEADER_NAMES:
        return render_document_header(element, state)  # rodzaj-aktu / data / ...
    if name.startswith("naglowek-"):
        return render_unit_heading(element, state)  # chapter/division heading
    if name == "zalacznik-nr":
        return render_attachment_number(element, state)
    if name == "zalacznik-binarny":
        return render_binary_attachment(element)
    if name == "attach-ref":
        return render_attached_text(element)
    if name in ("druk", "nr-druku"):
        return render_print_number(element, state)
    if name in UNIT_MARKERS:
        return render_numbered_unit(element, state)  # artykul / ustep / punkt / ...
    if name in SECTION_UNITS:
        return render_chapter_section(element, state)  # rozdzial / dzial / ...
    if name in TRANSPARENT_WRAPPERS:
        return render_wrapper(element, state)
    if name in CONTAINER_BLOCKS:
        return render_container_block(element, state)
    if name in TEXT_BLOCKS:
        return render_text_block(element, state, TEXT_BLOCKS[name], inline=inline)
    if name.startswith(("czesc-wspolna", "nie-ztp-czesc-wspolna")):
        return render_common_part(element, state)
    if name == "grafika":
        return render_raster_image(element, state)
    if name == "grafika-wektorowa":
        return render_vector_image(element, state)
    if name == "wzor-mat":
        return render_math_formula(element, state)
    if name in FORMULA_PARTS:
        return render_formula_part(element, state)  # wzor / opis / ... quoted on their own
    if name == "tabela":
        return render_table(element, state)
    if name in ("tr", "td"):
        return render_table_fragment(element, state)  # a row or cell quoted on its own

    return None

def _superscripts_html(text: str) -> Markup:
    """A unit number with its superscript index: the schema writes "2[1]" for 2¹."""
    return join(
        html_tag("sup", escape_text(piece)) if superscript else escape_text(piece)
        for piece, superscript in superscript_parts(text)
    )

def _nr_annotations(element: etree._Element, state: RenderState) -> Markup:
    """Footnote markers and comments attached inside the unit's ``<nr>`` (typical for TJ)."""
    for child in element:
        if is_element(child) and element_name(child) == "nr":
            return join(
                render_element(grandchild, state, inline=True)
                for grandchild in child
                if is_element(grandchild) and is_annotation(grandchild)
            )
    return Markup("")

def with_unit_state(element: etree._Element, css_class: str) -> str:
    """Append a ``stan--<value>`` class when the unit has a stan-jednostki (e.g. uchylony)."""
    stan = element.get("stan-jednostki")
    return f"{css_class} stan--{stan}" if stan else css_class

_UNIT_STATE_LABELS = {
    "uchylony": "uchylony",
    "utracil-moc": "utracił moc",
    "uznany-za-niewazny": "uznany za nieważny",
}

_PROVISION_CATEGORY_LABELS = {
    "przepis-zmieniajacy": "przepis zmieniający",
    "przepis-uchylajacy": "przepis uchylający",
    "przepis-o-wejsciu-w-zycie": "przepis o wejściu w życie",
    "przepis-opisujacy": "przepis opisujący",
    "definicja-legalna": "definicja legalna",
    "przepis-merytoryczny": "przepis merytoryczny",
    "przepis-karny": "przepis karny",
    "przepis-przejsciowy": "przepis przejściowy",
    "przepis-upowazniajacy": "przepis upoważniający",
    "przepis-odsylajacy": "przepis odsyłający",
}

_TIME_ATTRIBUTES = ("okres", "wejscie-w-zycie", "obowiazuje-do", "stan-jednostki")

def _unit_title_attributes(element: etree._Element, state: RenderState) -> dict[str, str] | None:
    """A tooltip with the unit's time (wejscie-w-zycie, okres, ...) and provision categories."""
    lines = _time_lines(element, state)
    categories = [
        label
        for attribute, label in _PROVISION_CATEGORY_LABELS.items()
        if _is_truthy(element.get(attribute))
    ]
    if categories:
        lines.append("Kategoria: " + ", ".join(categories))
    if element.get("rola") == "sankcja-karna":  # a common part that is the penalty clause
        lines.append("Sankcja karna")
    return {"title": "\n".join(lines)} if lines else None

def _time_lines(element: etree._Element, state: RenderState) -> list[str]:
    """When the unit is in force, read from its attributes and its period (@okres).

    @wejscie-w-zycie / @obowiazuje-do are the period projected onto dates; the
    period itself points at events in <DaneCzasowe>, which also cover events
    without a date (e.g. "z dniem wdrożenia rozwiązań technicznych").
    """
    events, groups = _time_index(element, state)
    period = groups.get(element.get("okres") or "")
    ranges = _period_ranges(period) if period is not None else {}
    start_id, end_id = ranges.pop("obowiazywanie", (None, None))
    start = format_date(element.get("wejscie-w-zycie") or "") or _event_text(events.get(start_id or ""))
    end = format_date(element.get("obowiazuje-do") or "") or _event_text(events.get(end_id or ""))
    lines = []
    if start:
        lines.append(f"Wejście w życie: {start}")
    if end:
        lines.append(f"Przestaje obowiązywać: {end}")
    for kind, (other_start, other_end) in ranges.items():
        lines.append(_range_text(_PERIOD_LABELS.get(kind, kind), events, other_start, other_end))
    stan = element.get("stan-jednostki")
    if stan:
        lines.append(f"Stan: {_UNIT_STATE_LABELS.get(stan, stan)}")
    return lines

def _time_index(
    element: etree._Element, state: RenderState
) -> tuple[dict[str, etree._Element], dict[str, etree._Element]]:
    """Events and periods (time groups) from the act's <DaneCzasowe>, by id; built once."""
    index = state.profile_data.get("time")
    if index is None:
        events: dict[str, etree._Element] = {}
        groups: dict[str, etree._Element] = {}
        for data in element.getroottree().getroot().iter(f"{{{SCHEMAPL}}}DaneCzasowe"):
            for event in data.iter(f"{{{SCHEMAPL}}}Zdarzenie"):
                events[event.get("id", "")] = event
            for group in data.iter(f"{{{SCHEMAPL}}}GrupaCzasowa"):
                groups[group.get("id", "")] = group
        index = state.profile_data["time"] = (events, groups)
    return index

def _period_ranges(group: etree._Element) -> dict[str, tuple[str | None, str | None]]:
    """A time group's ranges: kind (obowiazywanie, ...) -> (start event id, end event id)."""
    return {
        przedzial.get("rodzaj", ""): (przedzial.get("od"), przedzial.get("do"))
        for przedzial in group
        if is_element(przedzial) and element_name(przedzial) == "Przedzial"
    }

def _range_text(
    label: str, events: dict[str, etree._Element], start_id: str | None, end_id: str | None
) -> str:
    parts = [label]
    if start_id:
        parts.append("od " + _event_bound(events.get(start_id), start_id))
    if end_id:
        parts.append("do " + _event_bound(events.get(end_id), end_id))
    return " ".join(parts)

def _event_bound(event: etree._Element | None, event_id: str) -> str:
    """An event as a range bound: its date, else its condition or kind in quotes."""
    if event is None:
        return event_id
    if event.get("data"):
        return format_date(event.get("data"))
    kind = event.get("rodzaj", "")
    return f"„{event.get('warunek') or _EVENT_LABELS.get(kind, kind.replace('-', ' '))}”"

def _event_text(event: etree._Element | None) -> str:
    """When an event happens: its date, or the verbatim condition when it has none."""
    if event is None:
        return ""
    if event.get("data"):
        return format_date(event.get("data"))
    return event.get("warunek") or ""

def _time_differs_from_context(element: etree._Element) -> bool:
    """True when the element's time attributes differ from the nearest ancestor that has any."""
    own = tuple(element.get(name) for name in _TIME_ATTRIBUTES)
    if not any(own):
        return False
    for ancestor in element.iterancestors():
        inherited = tuple(ancestor.get(name) for name in _TIME_ATTRIBUTES)
        if any(inherited):
            return own != inherited
    return True

_PT_VALUE = re.compile(r"-?\d*(\.\d*)?pt")

_ALIGN_VALUES = {"left", "right", "center", "justify"}

_TYPO_PROPS = (
    "text-align",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "text-indent",
    "line-height",
)

def _typo_attributes(element: etree._Element) -> dict[str, str] | None:
    """Map the schema's validated typography attributes onto an inline style."""
    declarations = []
    for prop in _TYPO_PROPS:
        value = element.get(prop)
        if value is None:
            continue
        if prop == "text-align":
            if value in _ALIGN_VALUES:
                declarations.append(f"text-align:{value}")
        elif _PT_VALUE.fullmatch(value):
            declarations.append(f"{prop}:{value}")
    return {"style": ";".join(declarations)} if declarations else None

def render_paragraph(element: etree._Element, state: RenderState) -> Markup:
    # A <p> may contain a block quote, so use a <div> (a real <p> cannot).
    return html_tag(
        "div",
        render_children(element, state, inline=True),
        css_class="p",
        attributes=_typo_attributes(element),
    )

def render_flowing_text(element: etree._Element, state: RenderState) -> Markup:
    # <zdanie>/<tekst>: render the content so sentences flow. Every sentence may
    # repeat its unit's time; one whose time differs keeps it on a span.
    inner = render_children(element, state, inline=True)
    if _time_differs_from_context(element):
        return html_tag(
            "span",
            inner,
            css_class=with_unit_state(element, "zdanie"),
            attributes=_unit_title_attributes(element, state),
        )
    return inner

def render_inline_format(element: etree._Element, state: RenderState) -> Markup:
    tag = INLINE_FORMAT_TAGS[element_name(element)]
    return html_tag(tag, render_children(element, state, inline=True))

def render_inline_span(element: etree._Element, state: RenderState) -> Markup:
    css_class = INLINE_SPANS[element_name(element)]
    return html_tag("span", render_children(element, state, inline=True), css_class=css_class)

_SCRIPT_SCHEMES = ("javascript:", "vbscript:", "data:")

def _safe_href(url: str | None) -> str | None:
    """A link target from the document, or None when it is empty or could run script.

    The XML may come from an untrusted upload; browsers ignore whitespace inside
    the scheme, so "java script:" counts too.
    """
    value = (url or "").strip()
    if not value or "".join(value.split()).lower().startswith(_SCRIPT_SCHEMES):
        return None
    return value

def render_hyperlink(element: etree._Element) -> Markup:
    """<h>: the element's content IS the target URI."""
    uri = (element.text or "").strip()
    if not uri:
        return Markup("")
    href = _safe_href(uri)
    if href is None:
        return escape_text(uri)
    return html_tag("a", escape_text(uri), css_class="ref", attributes={"href": href})

def render_field(element: etree._Element, state: RenderState) -> Markup:
    """<pole>: a fill-in field.

    Shows the field's content; an empty field is resolved from the document's
    <metadane> (the @metadane XPath), falling back to the @data default.
    """
    inner = render_children(element, state, inline=True)
    if not str(inner).strip():
        inner = escape_text(field_value(element) or element.get("data") or "")
    if not str(inner).strip():
        return Markup("")
    styl = element.get("styl")
    if styl in INLINE_FORMAT_TAGS:  # e.g. styl="i" prints the value in italics
        inner = html_tag(INLINE_FORMAT_TAGS[styl], inner)
    return html_tag("span", inner, css_class="pole", attributes={"title": element.get("nazwa")})

def render_editorial_comment(
    element: etree._Element, state: RenderState, inline: bool
) -> Markup | None:
    """kmn:komentarz / kmn:uwaga: editorial notes, not part of the normative text."""
    name = element_name(element)
    if name == "komentarze":  # a container of kmn:komentarz
        return join(render_element(child, state, inline=inline) for child in element if is_element(child))
    if name not in ("komentarz", "uwaga"):
        return None
    label = "Komentarz" if name == "komentarz" else "Uwaga redakcyjna"
    if element.get("numer"):
        label += f" nr {element.get('numer')}"
    created = element.get("dataUtworzenia")
    details = [
        element.get("autor"),
        element.get("instytucjaAutora"),
        format_date(created) if created else None,
        "rozwiązany" if _is_truthy(element.get("rozwiazany")) else None,
        element.get("status") if element.get("status") in ("nieaktualny", "nieaktualna") else None,
    ]
    details_text = ", ".join(part for part in details if part)
    css = "komentarz"
    if _is_truthy(element.get("rozwiazany")) or element.get("status") in ("nieaktualny", "nieaktualna"):
        css += " komentarz--zamkniety"
    return html_tag(
        "span" if inline else "div",
        render_children(element, state, inline=True),
        css_class=css,
        attributes={"title": f"{label} ({details_text})" if details_text else label},
    )

def render_defined_term(element: etree._Element, state: RenderState) -> Markup:
    return html_tag("dfn", render_children(element, state, inline=True), css_class="definicja")

def render_reference(element: etree._Element, state: RenderState) -> Markup:
    inner = render_children(element, state, inline=True)
    if element_name(element) == "mref":  # a group of references joined by text
        return html_tag("span", inner, css_class="mref")
    link = _safe_href(_internal_link(element.get("href") or element.get("from"), element, state))
    if link:
        notes = []
        if element.get("upTo"):  # rref: a range of provisions
            notes.append(f"Zakres: {element.get('from')} – {element.get('upTo')}")
        version = element.get(f"{{{GUID_NS}}}GUIDwersji")
        if version:  # without it the reference is dynamic (follows the current text)
            notes.append(f"Odesłanie do wersji {version}")
        title = "\n".join(notes) or None
        return html_tag("a", inner, css_class="ref", attributes={"href": link, "title": title})
    return html_tag("span", inner, css_class="ref")

def _links(element: etree._Element, state: RenderState) -> InternalLinks:
    """The act's references to its own provisions (worked out once per document)."""
    links = state.profile_data.get("internal_links")
    if links is None:
        links = state.profile_data["internal_links"] = InternalLinks(element.getroottree().getroot())
    return links

def _internal_link(href: str | None, element: etree._Element, state: RenderState) -> str | None:
    """A reference to the act's own provision ("#art_13__pkt_7") points at its unit's anchor (the eId)."""
    value = (href or "").strip()
    if not value.startswith("#"):
        return href
    eid = _links(element, state).target(value, element)
    return "#" + eid if eid else href

def render_publication_reference(element: etree._Element) -> Markup:
    """<metryczka>: where an act was published, e.g. "Dz. U. z 2025 r. poz. 350" - as text, the XML links nothing."""
    return html_tag("span", escape_text("".join(element.itertext())), css_class="metryczka")

def render_person(element: etree._Element, inline: bool) -> Markup:
    """<osoba>: a person named in the text, or a signature line when it stands alone."""
    roles = []
    if _is_truthy(element.get("podpisujacy")):
        roles.append("podpisujący")
    if _is_truthy(element.get("upowaznienie")):
        roles.append("upoważniony do reprezentowania wnioskodawców")
    attributes = {"title": ", ".join(roles)} if roles else None
    name = escape_text(person_name(element))
    if inline:
        return html_tag("span", name, css_class="osoba", attributes=attributes)
    return html_tag("div", name, css_class="text-block podpis osoba", attributes=attributes)

def render_judge(element: etree._Element, state: RenderState) -> Markup:
    """<sedzia>: name plus the role from the rola attribute."""
    inner = render_children(element, state, inline=True)
    role = element.get("rola")
    if role:
        label = _JUDGE_ROLES.get(role, role)
        inner = inner + Markup(" ") + html_tag("span", escape_text(f"({label})"), css_class="sedzia__rola")
    return html_tag("div", inner, css_class="sedzia")

_JUDGE_ROLES = {
    "przewodniczacy": "przewodniczący",
    "sprawozdawca": "sprawozdawca",
    "czlonek": "członek",
    "skladajacy-zdanie-odrebne": "składający zdanie odrębne",
}

def _amendment_chip(element: etree._Element, *, block: bool = False) -> Markup:
    """A quiet, readable label for the amendment a quotation carries."""
    relevant = "funkcja" in element.attrib or any(
        key.startswith("{" + AMENDMENT_NS) for key in element.attrib
    )
    if not relevant:
        return Markup("")
    return _attribute_popup(element, amendment_label(element), block=block)

def render_inline_quotation(element: etree._Element, state: RenderState) -> Markup:
    prefix, suffix = quote_marks(element)
    state.anchor_suppression += 1
    try:
        inner = render_children(element, state, inline=True)
    finally:
        state.anchor_suppression -= 1
    inner = escape_text(prefix) + inner + escape_text(suffix)
    return html_tag("span", inner + _amendment_chip(element), css_class="cytat cytat--inline")

def render_block_quotation(element: etree._Element, state: RenderState) -> Markup:
    prefix, suffix = quote_marks(element)
    opening = html_tag("span", escape_text(prefix), css_class="cytat__open") if prefix else Markup("")
    closing = html_tag("span", escape_text(suffix), css_class="cytat__close") if suffix else Markup("")
    state.anchor_suppression += 1
    try:
        inner = render_children(element, state, inline=False)
    finally:
        state.anchor_suppression -= 1
    label = _amendment_chip(element, block=True)
    return html_tag("blockquote", label + opening + inner + closing, css_class="cytat")

def render_footnote(element: etree._Element, state: RenderState) -> Markup:
    key, symbol = _footnote_identity(element, state)
    link = html_tag("a", escape_text(symbol), attributes={"href": f"#fn-{key}"})

    if element_name(element) == "odnosnik":  # the footnote itself — collect its content
        collect_footnote(element, state)
        return html_tag("sup", link, css_class="fn-ref", attributes={"id": f"fnref-{key}"})

    # odsylacz-do-odnosnika: just a marker pointing at an existing footnote
    return html_tag("sup", link, css_class="fn-ref")

def _footnote_identity(element: etree._Element, state: RenderState) -> tuple[str, str]:
    """(key, symbol) of a footnote: its id/symbol, else its position."""
    position = len(state.footnotes) + 1
    key = element.get("id-odnosnika") or element.get("symbol") or f"przypis-{position}"
    symbol = element.get("symbol") or element.get("id-odnosnika") or str(position)
    return key, symbol

def collect_footnote(element: etree._Element, state: RenderState, *, placed: bool = True) -> None:
    """Add an <odnosnik> to the notes at the end; ``placed=False`` when it has no call site."""
    key, symbol = _footnote_identity(element, state)
    state.anchor_suppression += 1
    try:
        content = render_children(element, state, inline=False)
    finally:
        state.anchor_suppression -= 1
    state.footnotes.append(Footnote(key=key, symbol=symbol, content=content, placed=placed))

def _attribute_popup(element: etree._Element, title: str, *, block: bool = False) -> Markup:
    """A quiet marker whose hover popup lists the element's raw attributes.

    Inline form: a small ✎ mark. Block form: a muted pill showing the readable
    title itself (used above quoted amendment content).
    """
    rows = []
    for key, value in element.attrib.items():
        label = html_tag("span", escape_text(attribute_label(key, DISPLAY_PREFIXES)), css_class="nowela__key")
        shown = html_tag("span", escape_text(value), css_class="nowela__val")
        rows.append(html_tag("span", label + shown, css_class="nowela__row"))
    title_html = html_tag("strong", escape_text(title), css_class="nowela__title")
    popup = html_tag("span", title_html + join(rows), css_class="nowela__popup")
    if block:
        mark = html_tag("span", escape_text(title), css_class="nowela__pill")
        css = "nowela nowela--block"
    else:
        mark = html_tag("span", Markup("✎"), css_class="nowela__mark")
        css = "nowela"
    return html_tag("span", mark + popup, css_class=css, attributes={"tabindex": "0"})

def render_amendment_marker(element: etree._Element, state: RenderState) -> Markup:
    popup = _attribute_popup(element, amendment_label(element))
    if _has_child_elements(element):  # now:zastap carries the replacement content
        state.anchor_suppression += 1
        try:
            content = render_child_elements(element, state)
        finally:
            state.anchor_suppression -= 1
        return html_tag("span", popup + content, css_class="nowela-block")
    return render_children(element, state, inline=True) + popup

def render_math(element: etree._Element, state: RenderState, inline: bool) -> Markup:
    state.uses_math = True
    formula = Markup(_serialize_plain(element, MATHML))
    if inline:
        return html_tag("span", formula, css_class="math math--inline")
    return html_tag("div", formula, css_class="math")

_BLOCKED_FOREIGN_TAGS = {"script", "foreignObject"}

def _serialize_plain(element: etree._Element, namespace: str, *, is_root: bool = True) -> str:
    """Re-serialize a foreign subtree (MathML/SVG) with bare tag names.

    HTML parsers do not understand namespace prefixes, so ``mml:math`` becomes
    ``math`` with an ``xmlns`` on the root. Scripts, foreignObject and
    event-handler/javascript: attributes are dropped, because the XML may come
    from an untrusted upload.
    """
    name = element_name(element)
    if name in _BLOCKED_FOREIGN_TAGS:
        return ""
    parts = ["<", name]
    if is_root:
        parts.append(f' xmlns="{namespace}"')
    for key, value in element.attrib.items():
        attr = key.split("}", 1)[1] if key.startswith("{") else key
        if attr.lower().startswith("on") or value.strip().lower().startswith("javascript:"):
            continue
        parts.append(f' {attr}="{escape(value)}"')
    parts.append(">")
    if element.text:
        parts.append(str(escape(element.text)))
    for child in element:
        if is_element(child):
            parts.append(_serialize_plain(child, namespace, is_root=False))
        if child.tail:
            parts.append(str(escape(child.tail)))
    parts.append(f"</{name}>")
    return "".join(parts)

def _image_caption(element: etree._Element, state: RenderState) -> Markup | None:
    """The <opis-grafiki> printed under a picture, as a figcaption."""
    description = child_named(element, "opis-grafiki")
    if description is None:
        return None
    return html_tag("figcaption", render_children(description, state, inline=True))

def render_raster_image(element: etree._Element, state: RenderState) -> Markup:
    href = element.get("href", "")
    style = ""
    if element.get("width"):
        style += f"width:{element.get('width')};"
    if element.get("height"):
        style += f"height:{element.get('height')};"
    image = void_tag(
        "img",
        css_class="grafika",
        attributes={"src": href, "alt": element.get("alt", ""), "style": style or None},
    )
    caption = _image_caption(element, state) or html_tag("figcaption", escape_text(f"grafika: {href}"))
    return html_tag("figure", image + caption, css_class="grafika node--grafika")

def render_vector_image(element: etree._Element, state: RenderState) -> Markup:
    caption = _image_caption(element, state) or Markup("")
    for child in element:
        if is_element(child) and has_name(child, SVG, "svg"):
            svg = Markup(_serialize_plain(child, SVG))
            return html_tag("figure", svg + caption, css_class="grafika-wektorowa node--grafika-wektorowa")
    href = element.get("href")
    if href:
        image = void_tag("img", css_class="grafika", attributes={"src": href, "alt": "grafika wektorowa"})
        return html_tag("figure", image + caption, css_class="grafika node--grafika")
    return html_tag(
        "figure", Markup("[grafika wektorowa — brak treści]") + caption, css_class="grafika-wektorowa empty"
    )

def render_math_formula(element: etree._Element, state: RenderState) -> Markup:
    """<wzor-mat>: the formula (<wzor>), its lead-in and the descriptions of its symbols."""
    parts, descriptions = [], []
    for child in element:
        if not is_element(child):
            continue
        if element_name(child) == "opis":
            descriptions.append(_render_symbol_description(child, state))
        else:
            parts.append(render_element(child, state))  # wzor, wprowadzenie-do-opisu
    if descriptions:
        parts.append(html_tag("div", join(descriptions), css_class="wzor-mat__opisy"))
    return html_tag("figure", join(parts), css_class="wzor-mat")

def render_formula_part(element: etree._Element, state: RenderState) -> Markup:
    """One part of a <wzor-mat>; each may also stand alone in a cytat-blok (an amendment)."""
    name = element_name(element)
    if name == "wzor":
        return render_child_elements(element, state)  # the mml:math expression
    if name == "opis":
        return html_tag("div", _render_symbol_description(element, state), css_class="wzor-mat__opisy")
    if name == "objasnienie":
        return html_tag("div", render_child_elements(element, state), css_class="wzor-mat__objasnienie")
    # symbol-txt / symbol-mat
    return html_tag("span", render_children(element, state, inline=True), css_class="wzor-mat__symbol")

def _render_symbol_description(opis: etree._Element, state: RenderState) -> Markup:
    """One <opis>: the symbol (text or MathML) and its explanation."""
    symbol, explanation = [], []
    for child in opis:
        if not is_element(child):
            continue
        name = element_name(child)
        if name in ("symbol-txt", "symbol-mat"):
            symbol.append(render_children(child, state, inline=True))
        elif name == "objasnienie":
            explanation.append(render_child_elements(child, state))
        else:
            explanation.append(render_element(child, state))
    symbol_html = (
        html_tag("span", join(symbol), css_class="wzor-mat__symbol") if symbol else Markup("")
    )
    explanation_html = html_tag("div", join(explanation), css_class="wzor-mat__objasnienie")
    return html_tag("div", symbol_html + explanation_html, css_class="wzor-mat__opis")

def render_table(element: etree._Element, state: RenderState) -> Markup:
    """<tabela>: rows live under <tbody> (the schema) or directly (leniency).

    The <opis-tabeli> legend is printed under the table; anything else goes above it.
    """
    rows: list[Markup] = []
    captions: list[Markup] = []
    legends: list[Markup] = []
    _collect_table_rows(element, state, rows, captions, legends)
    attributes = None
    width = element.get("width")
    if width and re.fullmatch(r"\d+%", width):
        attributes = {"style": f"width:{width}"}
    table = html_tag("table", join(rows), css_class="tabela", attributes=attributes)
    if captions or legends:
        return html_tag("div", join(captions) + table + join(legends), css_class="node--tabela")
    return table

def _collect_table_rows(
    container: etree._Element,
    state: RenderState,
    rows: list[Markup],
    captions: list[Markup],
    legends: list[Markup],
) -> None:
    for child in container:
        if not is_element(child):
            continue
        name = element_name(child)
        if name in ("tbody", "thead", "tfoot"):
            _collect_table_rows(child, state, rows, captions, legends)
        elif name == "tr":
            rows.append(_render_table_row(child, state))
        elif name == "opis-tabeli":
            legends.append(render_element(child, state))
        else:
            captions.append(render_element(child, state))

def render_table_fragment(element: etree._Element, state: RenderState) -> Markup:
    """A <tr> or <td> standing alone (quoted in a cytat-blok), shown as a small table."""
    if element_name(element) == "tr":
        row = _render_table_row(element, state)
    else:
        row = html_tag("tr", _render_table_cell(element, state, header=False))
    return html_tag("table", row, css_class="tabela")

def _render_table_row(row: etree._Element, state: RenderState) -> Markup:
    header_row = _is_truthy(row.get("naglowek"))
    cells = []
    for cell in row:
        if not is_element(cell):
            continue
        name = element_name(cell)
        if name in ("td", "th"):
            cells.append(_render_table_cell(cell, state, header=header_row or name == "th"))
        else:  # leniency: any other child treated as a one-element cell
            tag = "th" if name == "tytul-kolumny" else "td"
            cells.append(html_tag(tag, render_element(cell, state)))
    return html_tag("tr", join(cells))

def _render_table_cell(cell: etree._Element, state: RenderState, *, header: bool) -> Markup:
    attributes: dict[str, str] = {}
    for span_attr in ("colspan", "rowspan"):
        value = cell.get(span_attr)
        if value and value.isdigit() and int(value) > 1:
            attributes[span_attr] = value
    style = []
    width = cell.get("width")
    if width and re.fullmatch(r"\d+%", width):
        style.append(f"width:{width}")
    valign = cell.get("vertical-align")
    if valign in ("top", "middle", "bottom"):
        style.append(f"vertical-align:{valign}")
    if style:
        attributes["style"] = ";".join(style)
    header = header or _contains_only_column_titles(cell)
    tag = "th" if header else "td"
    return html_tag(tag, render_children(cell, state, inline=False), attributes=attributes or None)

def _contains_only_column_titles(cell: etree._Element) -> bool:
    children = [child for child in cell if is_element(child)]
    return bool(children) and all(element_name(child) == "tytul-kolumny" for child in children)

def render_title(element: etree._Element, state: RenderState) -> Markup:
    """<tytul> means three different things, depending on its parent."""
    parent = element.getparent()
    parent_name = element_name(parent) if parent is not None else ""
    if parent_name in ACT_TITLE_PARENTS:
        return render_document_header(element, state)  # the act's own title
    if parent_name in ("ksiega", "ksiega-n"):
        return render_chapter_section(element, state)  # systematization unit "Tytuł"
    return render_text_block(element, state, "unit-title")  # an article's title

def render_document_header(element: etree._Element, state: RenderState) -> Markup:
    inner = render_children(element, state, inline=True)
    if not str(inner).strip():
        return Markup("")  # amending acts have empty rodzaj-aktu / data / tytul
    return html_tag("div", inner, css_class=DOCUMENT_HEADER_CLASS[element_name(element)])

def collect_metadata(element: etree._Element, state: RenderState) -> Markup:
    """Render <metadane> into the sidebar panel; show nothing in the main content.

    Footnotes kept in <AparatOdnosnikow> (their call site cannot be shown in the
    text) are added to the notes at the end instead.
    """
    events, _ = _time_index(element, state)
    entries = []
    for child in element:
        if not is_element(child):
            continue
        if element_name(child) == "AparatOdnosnikow":
            for note in child:
                if is_element(note) and element_name(note) == "odnosnik":
                    collect_footnote(note, state, placed=False)
            continue
        entries.append(_metadata_entry(child, events))
    state.metadata_html = join(entries)
    return Markup("")

_META_LABELS = {
    "ELIaktu": "Identyfikator ELI",
    "ELI": "ELI",
    "ELIDL": "ELI DL",
    "ELIDLrezultatProjektu": "ELI DL — rezultat projektu",
    "ELIDLdotyczyAktu": "ELI DL — dotyczy aktu",
    "GUIDwersji": "GUID wersji",
    "AdresISAP": "Adres ISAP",
    "Wydawnictwo": "Wydawnictwo",
    "Rok": "Rok",
    "NrDziennika": "Nr dziennika",
    "Pozycja": "Pozycja",
    "AdresWyswietlany": "Adres publikacyjny",
    "Tytul": "Tytuł",
    "Rodzaj": "Rodzaj aktu",
    "TytulyPoprzednie": "Tytuły poprzednie",
    "TytulPoprzedni": "Tytuł poprzedni",
    "DataOgloszenia": "Data ogłoszenia",
    "DataAktu": "Data aktu",
    "DataProjektu": "Data projektu",
    "DataWydania": "Data wydania",
    "DataWersjiProjektu": "Data wersji projektu",
    "DaneCzasowe": "Dane czasowe",
    "CyklZyciaAktu": "Cykl życia aktu",
    "CyklZyciaProjektuUstawyLubKodeksu": "Przebieg prac nad projektem",
    "DataObowiazywaniaWersji": "Obowiązywanie wersji",
    "DataStanuPrawnegoTJ": "Stan prawny tekstu jednolitego",
    "DataOstatniejZmiany": "Ostatnia zmiana",
    "Status": "Status",
    "CzyObowiazuje": "Obowiązywanie",
    "Organy": "Organy",
    "OrganyInicjujace": "Organy inicjujące",
    "Organ": "Organ",
    "Nazwa": "Nazwa",
    "OrganPodpisujacy": "Organ podpisujący",
    "OrganInicjujacy": "Organ inicjujący",
    "OsobaPodpisujaca": "Osoba podpisująca",
    "Uwagi": "Uwagi",
    "Podpis": "Podpis elektroniczny",
    "NrSeryjny": "Nr seryjny",
    "Osoba": "Osoba",
    "Zakres": "Zakres",
    "DataPodpisu": "Data podpisu",
    "SlowaKluczowe": "Słowa kluczowe",
    "NazwyWlasne": "Nazwy własne",
    "Relacje": "Relacje z innymi aktami",
    "TekstJednolityBazowy": "Tekst jednolity bazowy",
    "FlagaKonsolidacyjna": "Konsolidacja",
    "AktyUE": "Akty UE",
    "AktUE": "Akt UE",
    "ELI-EU": "ELI UE",
    "TytulAktu": "Tytuł aktu",
    "TekstyAktu": "Pliki tekstu aktu",
    "TekstAktu": "Plik",
    "NazwaPliku": "Nazwa pliku",
    "TypTekstu": "Typ tekstu",
    "DrukiSejmowe": "Druki sejmowe",
    "DrukSejmowy": "Druk sejmowy",
    "NumerDruku": "Numer druku",
    "Kadencja": "Kadencja",
    "ELI_DL": "ELI DL",
    "LinkDruku": "Link do druku",
    "LinkDrukuAPI": "Link do druku (API)",
    "LinkProcesuAPI": "Link do procesu (API)",
}

_RELATION_LABELS = {
    "PodstawaPrawna": "Podstawa prawna",
    "PodstawaPrawnaJednostka": "Podstawa prawna (jednostka)",
    "Zmienia": "Zmienia",
    "Prostuje": "Prostuje",
    "ZmieniaWZ": "Zmienia (w związku)",
    "JestZmienianyPrzez": "Zmieniany przez",
    "JestZmienianyPrzezWZ": "Zmieniany (w związku) przez",
    "JestProstowanyPrzez": "Prostowany przez",
    "Uchyla": "Uchyla",
    "UchylaPosrednio": "Uchyla pośrednio",
    "UchylaGeneralnie": "Uchyla generalnie",
    "JestUchylany": "Uchylany przez",
    "JestUchylanyPosrednio": "Uchylany pośrednio przez",
    "JestUchylanyGeneralnie": "Uchylany generalnie przez",
    "Wykonuje": "Wykonuje",
    "JestWykonywany": "Wykonywany przez",
    "Odsyla": "Odsyła do",
    "OrzeczeniaTK": "Orzeczenia TK",
    "OrzeczenieTKDlaAktu": "Orzeczenie TK dla aktu",
    "Ujednolica": "Ujednolica",
    "JestUjednolicany": "Ujednolicany przez",
    "Wprowadza": "Wprowadza",
    "JestWprowadzany": "Wprowadzany przez",
}

_EVENT_LABELS = {
    "stosowanie-z-moca-wsteczna": "stosowanie z mocą wsteczną",
    "wejscie-w-zycie": "wejście w życie",
    "uchylenie": "uchylenie",
    "utrata-mocy": "utrata mocy",
    "stwierdzenie-niewaznosci": "stwierdzenie nieważności",
    "ujednolicenie": "ujednolicenie",
    "wpłyniecie-pisma": "wpłynięcie pisma",
    "doreczenie-druku": "doręczenie druku",
    "skierowano-do-opinii-do-organizacji-samorządowych": "skierowanie do opinii organizacji samorządowych",
    "skierowano-do-pierwszego-czytania-w-komisjach": "skierowanie do pierwszego czytania w komisjach",
    "pierwsze-czytanie-w-komisjach": "pierwsze czytanie w komisjach",
    "sprawozdanie-komisji": "sprawozdanie komisji",
    "drugie-czytanie-na-posiedzeniu-Sejmu": "drugie czytanie na posiedzeniu Sejmu",
    "trzecie-czytanie-na-posiedzeniu-Sejmu": "trzecie czytanie na posiedzeniu Sejmu",
    "ustawe-przekazano-Prezydentowi-i-Marszalkowi-Senatu": "przekazanie ustawy Prezydentowi i Marszałkowi Senatu",
    "stanowisko-Senatu": "stanowisko Senatu",
    "rozpatrywanie-na-forum-Sejmu-stanowiska-Senatu": "rozpatrzenie przez Sejm stanowiska Senatu",
    "ustawe-przekazano-Prezydentowi-do-podpisu": "przekazanie ustawy Prezydentowi do podpisu",
    "Prezydent-podpisal-ustawe": "podpisanie ustawy przez Prezydenta",
}

_EVENT_ORIGIN_LABELS = {"odczytane": "odczytane z aktu", "domyslne-z-aktu": "reguła domyślna"}

_PERIOD_LABELS = {
    "obowiazywanie": "Obowiązywanie",
    "stosowanie-z-moca-wsteczna": "Stosowanie z mocą wsteczną",
    "przed-pierwszym-czytaniem": "Przed pierwszym czytaniem",
    "pierwsze-czytanie": "Pierwsze czytanie",
    "ujednolicenie": "Ujednolicenie",
}


_ORGAN_ROLE_LABELS = {
    "wydajacy": "wydający",
    "podpisujacy": "podpisujący",
    "opiniujacy": "opiniujący",
    "uzgadniajacy": "uzgadniający",
    "za zgoda": "za zgodą",
}

_TEXT_TYPE_LABELS = {
    "O": "oryginał",
    "H": "HTML",
    "I": "PDF (ISAP)",
    "T": "tekst Kancelarii Sejmu",
    "U": "tekst ujednolicony (ISAP)",
}

_IN_FORCE_LABELS = {"IN_FORCE": "obowiązuje", "NOT_IN_FORCE": "nie obowiązuje"}

_META_LINK_NAMES = {
    "ELI",
    "ELIDL",
    "ELIDLrezultatProjektu",
    "ELIDLdotyczyAktu",
    "ELI-EU",
    "ELI_DL",
    "LinkDruku",
    "LinkDrukuAPI",
    "LinkProcesuAPI",
}

def _meta_label(element: etree._Element) -> str:
    return _META_LABELS.get(element_name(element), display_label(element, DISPLAY_PREFIXES))

def _format_meta_value(name: str, text: str) -> str:
    if name.startswith("Data"):
        return format_date(text)
    if name == "Rodzaj":
        return ACT_TYPE_LABELS.get(text, text)
    if name == "CzyObowiazuje":
        return _IN_FORCE_LABELS.get(text, text)
    if name == "TypTekstu":
        return _TEXT_TYPE_LABELS.get(text, text)
    if name == "FlagaKonsolidacyjna":
        return {"true": "tak", "1": "tak", "false": "nie", "0": "nie"}.get(text, text)
    return text

def _eli_href(value: str) -> str | None:
    """A clickable address for an ELI: absolute URLs as-is, bare paths via eli.gov.pl."""
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    if "/" in value:
        path = value[4:] if value.startswith("eli/") else value
        return "https://eli.gov.pl/eli/" + path.lstrip("/")
    return None

def _metadata_value_html(name: str, text: str) -> Markup:
    if name in _META_LINK_NAMES:
        href = _eli_href(text)
        if href:
            return html_tag("a", escape_text(text), attributes={"href": href, "rel": "noopener"})
    return escape_text(_format_meta_value(name, text))

def _metadata_row(label: str, value: Markup) -> Markup:
    key = html_tag("span", escape_text(label), css_class="meta-key")
    return html_tag("div", key + html_tag("span", value, css_class="meta-val"), css_class="meta-row")

def _metadata_group(label: str, inner: Markup) -> Markup:
    """A collapsible group of fields; nothing when it would be empty."""
    if not str(inner).strip():
        return Markup("")
    summary = html_tag("summary", escape_text(label))
    return html_tag("details", summary + inner, css_class="meta-group")

def _metadata_entry(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """One metadata field: a key/value row, or a collapsible group of fields."""
    name = element_name(element)
    if name == "Relacje":
        return _metadata_relations(element, events)
    if name == "DaneCzasowe":
        return _metadata_time(element, events)
    if name == "DataObowiazywaniaWersji":
        return _metadata_version_validity(element, events)
    if name == "DataOstatniejZmiany":  # an event id, not a date
        event_id = (element.text or "").strip()
        return _metadata_row(_meta_label(element), escape_text(_event_text(events.get(event_id)) or event_id))
    if name == "Organ":
        return _metadata_organ(element, events)
    if name == "OsobaPodpisujaca":
        return _metadata_row(_meta_label(element), escape_text(person_name(element)))
    if name in ("SlowaKluczowe", "NazwyWlasne", "TytulyPoprzednie"):
        return _metadata_term_list(element)
    children = [child for child in element if is_element(child)]
    if not children:
        text = (element.text or "").strip()
        if not text:
            return Markup("")
        return _metadata_row(_meta_label(element), _metadata_value_html(name, text))
    # A group with a single simple field reads better as one flat row
    # (e.g. DataAktu -> "Data wydania: ...", ELIaktu -> "ELI: ...").
    if len(children) == 1 and not any(is_element(grandchild) for grandchild in children[0]):
        return _metadata_entry(children[0], events)
    return _metadata_group(_meta_label(element), join(_metadata_entry(child, events) for child in children))

def _eli_display(eli: str) -> str:
    """A compact publication address for a bare ELI, e.g. "Dz.U. 1934 poz. 834"."""
    path = eli
    for prefix in ("https://eli.gov.pl/eli/", "http://eli.gov.pl/eli/", "eli/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    parts = [part for part in path.strip("/").split("/") if part]
    journals = {"DU": "Dz.U.", "MP": "M.P."}
    if len(parts) >= 3 and parts[0] in journals and parts[1].isdigit() and parts[2].isdigit():
        return f"{journals[parts[0]]} {parts[1]} poz. {parts[2]}"
    return eli

def _metadata_relations(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """<Relacje>: the act's relations, grouped by their kind (Zmienia, Uchyla, ...)."""
    by_kind: dict[str, list[Markup]] = {}
    for relation in element:
        if is_element(relation) and element_name(relation) == "Relacja":
            by_kind.setdefault(relation.get("typ", ""), []).append(_metadata_relation(relation, events))
    groups = [
        _metadata_group(f"{_RELATION_LABELS.get(kind, kind)} ({len(items)})", join(items))
        for kind, items in by_kind.items()
    ]
    return _metadata_group(_meta_label(element), join(groups))

def _metadata_relation(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """One <Relacja>: the related act as a link, with this act's unit and the date appended."""
    eli = element.get("ELI", "")
    title = element.get("tytul") or (_eli_display(eli) if eli else "")
    if not title:
        return Markup("")
    href = _eli_href(eli) if eli else None
    main = (
        html_tag("a", escape_text(title), attributes={"href": href, "rel": "noopener"})
        if href
        else escape_text(title)
    )
    extras = []
    if element.get("eId"):
        extras.append(format_eid(element.get("eId")) or element.get("eId"))
    event_id = element.get("dataRelacji")
    if event_id:  # the event the relation comes with, e.g. its entry into force
        extras.append(_event_text(events.get(event_id)) or event_id)
    extra_html = (
        html_tag("span", escape_text(" (" + ", ".join(extras) + ")"), css_class="meta-extra")
        if extras
        else Markup("")
    )
    return html_tag("div", main + extra_html, css_class="meta-item")

def _metadata_time(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """<DaneCzasowe>: the act's events (with the units they concern) and its periods."""
    sections, periods = [], []
    for child in element:
        if not is_element(child):
            continue
        if element_name(child) == "GrupaCzasowa":
            periods.append(_metadata_period(child, events))
        else:  # CyklZyciaAktu / CyklZyciaProjektuUstawyLubKodeksu
            items = join(_metadata_event(event) for event in child if is_element(event))
            sections.append(_metadata_group(_meta_label(child), items))
    sections.append(_metadata_group("Okresy", join(periods)))
    return _metadata_group(_meta_label(element), join(sections))

def _metadata_event(event: etree._Element) -> Markup:
    """One <Zdarzenie>: when and what, where it was read from, and the units it concerns."""
    kind = event.get("rodzaj", "")
    what = _EVENT_LABELS.get(kind, kind.replace("-", " "))
    when = _event_text(event)
    extras = [
        event.get("warunek") if event.get("data") else None,  # without a date it is the headline
        event.get("podstawa"),
        _EVENT_ORIGIN_LABELS.get(event.get("pochodzenie") or ""),
    ]
    extra_text = "; ".join(extra for extra in extras if extra)
    extra_html = (
        html_tag("span", escape_text(f" ({extra_text})"), css_class="meta-extra") if extra_text else Markup("")
    )
    units = [
        _metadata_event_unit(unit)
        for unit in event
        if is_element(unit) and element_name(unit) == "JednostkaAktu"
    ]
    headline = escape_text(f"{when} — {what}" if when else what)
    return html_tag(
        "div",
        headline + extra_html + _metadata_group(f"Jednostki ({len(units)})", join(units)),
        css_class="meta-item",
    )

def _metadata_event_unit(unit: etree._Element) -> Markup:
    """A <JednostkaAktu>, with the units of the amended text it is limited to or excludes."""
    text = format_eid(unit.get("eId", "")) or unit.get("eId", "")
    for kind, phrase in (("JednostkaWZakresie", "w zakresie"), ("JednostkaWWylaczeniu", "z wyłączeniem")):
        targets = []
        for scope in unit:
            if not (is_element(scope) and element_name(scope) == kind):
                continue
            if scope.get("eId"):
                targets.append(format_eid(scope.get("eId")))
            targets.extend(
                topic.get("ZakresMerytoryczny")
                for topic in scope
                if is_element(topic) and topic.get("ZakresMerytoryczny")
            )
        if targets:
            text += f" — {phrase}: {', '.join(targets)}"
    return html_tag("div", escape_text(text), css_class="meta-item")

def _metadata_period(group: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """One <GrupaCzasowa>: its ranges spelled out with the events' dates."""
    ranges = [
        _range_text(_PERIOD_LABELS.get(kind, kind), events, start_id, end_id)
        for kind, (start_id, end_id) in _period_ranges(group).items()
    ]
    text = "; ".join(ranges) or group.get("id", "")
    if _is_truthy(group.get("glowna")):
        text += " (główny okres aktu)"
    return html_tag("div", escape_text(text), css_class="meta-item")

def _metadata_version_validity(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """<DataObowiazywaniaWersji>: Od/Do name events; show their dates."""
    start, end = child_named(element, "Od"), child_named(element, "Do")
    text = _range_text(
        "",
        events,
        (start.text or "").strip() if start is not None else None,
        (end.text or "").strip() if end is not None else None,
    ).strip()
    return _metadata_row(_meta_label(element), escape_text(text)) if text else Markup("")

def _metadata_organ(element: etree._Element, events: dict[str, etree._Element]) -> Markup:
    """One <Organ>: "Nazwa (rola)" headline plus any signature details below."""
    headline = ""
    rest = []
    for child in element:
        if not is_element(child):
            continue
        if element_name(child) == "Nazwa":
            headline = (child.text or "").strip()
        else:
            rest.append(_metadata_entry(child, events))
    role = element.get("rola")
    if role:
        role = _ORGAN_ROLE_LABELS.get(role, role)
        headline = f"{headline} ({role})" if headline else role
    rows = []
    if headline:
        rows.append(html_tag("div", escape_text(headline), css_class="meta-item"))
    rows.extend(rest)
    return join(rows)

def _metadata_term_list(element: etree._Element) -> Markup:
    """Keyword-style lists shown as one comma-separated row."""
    terms = [(child.text or "").strip() for child in element if is_element(child)]
    terms = [term for term in terms if term]
    if not terms:
        return Markup("")
    return _metadata_row(_meta_label(element), escape_text(", ".join(terms)))

def render_numbered_unit(element: etree._Element, state: RenderState) -> Markup:
    name = element_name(element)
    marker = UNIT_MARKERS[name](number_of(element))
    attributes = _unit_title_attributes(element, state) or {}
    if name in ARTICLE_TOC_NAMES:
        anchor = _register_anchor(element, state, "art")
        if anchor:
            attributes["id"] = anchor
            state.toc.append(
                TocEntry(
                    anchor=anchor,
                    marker=superscripts_text(marker),
                    title=plain_text(child_named(element, "tytul")),
                    kind="article",
                    depth=state.toc_depth,
                )
            )
    elif (element.get("eId") or "").strip() in _links(element, state).eids:
        # a point, letter, ... the act refers to: its eId is the references' target
        anchor = _register_anchor(element, state, "unit")
        if anchor:
            attributes["id"] = anchor
    marker_html = html_tag(
        "span", _superscripts_html(marker) + _nr_annotations(element, state), css_class="unit__marker"
    )
    body_html = html_tag(
        "div", render_child_elements(element, state, skip={"nr"}), css_class="unit__body"
    )
    classes = with_unit_state(element, f"unit unit--{name} collapsible")
    return html_tag("div", marker_html + body_html, css_class=classes, attributes=attributes or None)

def render_chapter_section(element: etree._Element, state: RenderState) -> Markup:
    name = element_name(element)
    attributes = _unit_title_attributes(element, state) or {}
    anchor = _register_anchor(element, state, "sect")
    if anchor:
        attributes["id"] = anchor
        marker, title = section_outline(element)
        state.toc.append(
            TocEntry(
                anchor=anchor,
                marker=marker or name,
                title=title,
                kind="section",
                depth=state.toc_depth,
            )
        )
    heading, body = [], []
    state.toc_depth += 1
    try:
        for child in element:
            if not is_element(child):
                continue
            child_name = element_name(child)
            if child_name == "nr":
                continue
            if child_name.startswith("naglowek-"):
                heading.append(render_element(child, state))
            else:
                body.append(render_element(child, state))
    finally:
        state.toc_depth -= 1
    body_html = html_tag("div", join(body), css_class="sect__body")
    classes = with_unit_state(element, f"sect sect--{name} collapsible")
    return html_tag(
        "section", join(heading) + body_html, css_class=classes, attributes=attributes or None
    )

def render_wrapper(element: etree._Element, state: RenderState) -> Markup:
    name = element_name(element)
    classes = with_unit_state(element, f"wrapper wrapper--{name}")
    # An implicit unit (ustep-n, dzial-n, ...) usually shares its parent's time; show it only when not.
    attributes = _unit_title_attributes(element, state) if _time_differs_from_context(element) else None
    return html_tag("div", render_child_elements(element, state), css_class=classes, attributes=attributes)

def render_container_block(element: etree._Element, state: RenderState) -> Markup:
    """A block container (preambula, uzasadnienie, zalacznik, ...) with block children."""
    name = element_name(element)
    css = CONTAINER_BLOCKS[name]
    attributes = _unit_title_attributes(element, state) or {}
    if name in ("zalacznik", "uzasadnienie"):  # jump points for the outline
        anchor = _register_anchor(element, state, "blk")
        if anchor:
            attributes["id"] = anchor
            if name == "zalacznik":
                number = number_of(element)
                nr_child = child_named(element, "zalacznik-nr")
                if not number and nr_child is not None:
                    number = number_of(nr_child)
                marker = superscripts_text(f"Załącznik nr {number}" if number else "Załącznik")
                title = plain_text(child_named(element, "tytul-zalacznika"))
            else:
                marker = "Uzasadnienie"
                title = plain_text(child_named(element, "tytul-uzasadnienia"))
            state.toc.append(
                TocEntry(anchor=anchor, marker=marker, title=title, kind="block", depth=0)
            )
    classes = with_unit_state(element, f"block block--{css}")
    return html_tag(
        "section", render_child_elements(element, state), css_class=classes,
        attributes=attributes or None,
    )

def render_text_block(
    element: etree._Element, state: RenderState, css_class: str, *, inline: bool = False
) -> Markup:
    """One block of running text (JednostkaTekstowaTyp): text plus inline children."""
    inner = render_children(element, state, inline=True)
    if not str(inner).strip():
        return Markup("")
    tag = "span" if inline else "div"
    return html_tag(
        tag, inner, css_class=f"text-block {css_class}", attributes=_typo_attributes(element)
    )

def render_special(element: etree._Element, state: RenderState, inline: bool) -> Markup:
    """<specjalny>: free-form formatted text; block or inline depending on context."""
    tag = "span" if inline else "div"
    return html_tag(
        tag,
        render_children(element, state, inline=True),
        css_class="specjalny",
        attributes=_typo_attributes(element),
    )

def render_common_part(element: etree._Element, state: RenderState) -> Markup:
    return html_tag(
        "div",
        render_child_elements(element, state, skip={"nr"}),
        css_class=with_unit_state(element, "common-part"),
        attributes=_unit_title_attributes(element, state),
    )

def render_unit_heading(element: etree._Element, state: RenderState) -> Markup:
    suffix = element_name(element)[len("naglowek-") :]
    word = HEADING_WORDS.get(suffix, "")
    marker = f"{word} {number_of(element)}".strip()

    # The heading title: mixed content (naglowek-skladu etc. hold bare text)
    # and/or <p> children (systematization headings).
    title_parts: list[Markup] = []
    if element.text and element.text.strip():
        title_parts.append(escape_text(element.text))
    for child in element:
        if is_element(child):
            child_name = element_name(child)
            if child_name in ("nr", "akapit"):
                pass
            elif child_name == "p":
                title_parts.append(render_children(child, state, inline=True))
            else:
                title_parts.append(render_element(child, state, inline=True))
        if child.tail and child.tail.strip():
            title_parts.append(escape_text(child.tail))

    annotations = _nr_annotations(element, state)
    marker_html = (
        html_tag("span", _superscripts_html(marker) + annotations, css_class="heading__marker")
        if marker or str(annotations)
        else Markup("")
    )
    title_html = html_tag("span", join(title_parts), css_class="heading__title")
    return html_tag("div", marker_html + title_html, css_class=f"heading heading--{suffix}")

def render_attachment_number(element: etree._Element, state: RenderState) -> Markup:
    """<zalacznik-nr>: the "Załącznik nr X" line at the top of an attachment."""
    number = number_of(element)
    label = f"Załącznik nr {number}" if number else "Załącznik"
    return html_tag(
        "div", _superscripts_html(label) + _nr_annotations(element, state), css_class="zalacznik-nr"
    )

def render_binary_attachment(element: etree._Element) -> Markup:
    """<zalacznik-binarny>: an empty element pointing at an external file."""
    href = element.get("href")
    if href:
        link = html_tag("a", escape_text(href), css_class="ref", attributes={"href": _safe_href(href)})
        return html_tag("div", escape_text("Załącznik binarny: ") + link, css_class="zalacznik-binarny")
    return html_tag(
        "div", escape_text("Załącznik binarny (brak odwołania do pliku)"), css_class="zalacznik-binarny"
    )

def render_attached_text(element: etree._Element) -> Markup:
    """<attach-ref>: the consolidated text announced by an obwieszczenie, published as its own act."""
    href = element.get("href", "")
    kind = ACT_TYPE_LABELS.get(element.get("rodzaj") or "")
    label = f"Tekst jednolity ({kind}): " if kind else "Tekst jednolity: "
    link = html_tag("a", escape_text(href), css_class="ref", attributes={"href": _safe_href(href)})
    return html_tag("div", escape_text(label) + link, css_class="zalacznik-binarny")

def render_print_number(element: etree._Element, state: RenderState) -> Markup:
    """<druk> ("Druk nr") and the <nr-druku> after it, printed as one line."""
    if element_name(element) == "nr-druku":
        previous = sibling_element(element, following=False)
        if previous is not None and element_name(previous) == "druk":
            return Markup("")  # already printed with its <druk>
        return render_text_block(element, state, "druk")
    inner = render_children(element, state, inline=True)
    following = sibling_element(element, following=True)
    if following is not None and element_name(following) == "nr-druku":
        inner += Markup(" ") + escape_text((following.text or "").strip())
    return html_tag("div", inner, css_class="text-block druk")

def render_xmldsig(element: etree._Element, state: RenderState) -> Markup:
    """An XMLDSig signature: shown as a compact, collapsed technical note."""
    summary = html_tag("summary", escape_text(f"Podpis elektroniczny ({display_label(element, DISPLAY_PREFIXES)})"))
    inner = render_unknown_element(element, state, inline=False)
    return html_tag("details", summary + inner, css_class="e-podpis")

class SchemaPLProfile:
    """Renders schemaPL elements; returns None for anything it does not handle."""

    display_prefixes = DISPLAY_PREFIXES
    root_namespaces = frozenset({SCHEMAPL})

    def dispatch(self, element: etree._Element, state: RenderState, inline: bool) -> Markup | None:
        return dispatch(element, state, inline)


PROFILE = SchemaPLProfile()

