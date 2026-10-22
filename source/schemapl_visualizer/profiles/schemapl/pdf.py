"""schemaPL → PDF: an act typeset straight from its XML.

The walk turns the act into the sequence of paragraphs its publication
has, each with the paragraph style Word gives it ("PKT", "Z_LIT/UST(§)",
...), its marker ("1)", "Art. 5.") and its place in the structure. The
layout template ``dziennik.typ`` then draws them as published in the
official journal, or - the accessible version - as the same document in
large print, tagged for screen readers (PDF/UA-1). Both get the same
code; only the template's ``uklad`` input differs.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date
from functools import cache
from typing import TypeAlias

from lxml import etree

from ...namespaces import element_name, element_namespace, is_element
from ...pdf.mathml import spoken, typst_math
from ...pdf.typst import TEMPLATE_DIR, Code, Inline, call, literal, string
from .common import (
    ACT_TYPE_LABELS,
    AMENDMENT_NS,
    COMMENTS_NS,
    HEADING_WORDS,
    MATHML,
    SCHEMAPL,
    SVG,
    TYPOGRAPHY_NS,
    UNIT_MARKERS,
    InternalLinks,
    child_named,
    field_value,
    is_annotation,
    number_of,
    number_text,
    person_name,
    plain_text,
    quote_marks,
    sibling_element,
    superscript_parts,
    superscripts_text,
)

# -- styles ------------------------------------------------------------

UNIT_STYLES = {
    "artykul": "ART(§)",
    "artykul-kodeksu": "ART(§)",
    "artykul-tj": "ART(§)",
    "artykul-kodeksu-tj": "ART(§)",
    "nie-ztp-artykul": "ART(§)",
    "paragraf": "ART(§)",
    "paragraf-tj": "ART(§)",
    "nie-ztp-paragraf-rozporzadzenia": "ART(§)",
    "ustep": "UST(§)",
    "nie-ztp-ustep": "UST(§)",
    "paragraf-kodeksu": "UST(§)",
    "nie-ztp-paragraf-kodeksu": "UST(§)",
    "punkt": "PKT",
    "nie-ztp-punkt": "PKT",
    "litera": "LIT",
    "nie-ztp-litera": "LIT",
    "tiret": "TIR",
    "nie-ztp-tiret": "TIR",
    "podw-tiret": "2TIR",
    "nie-ztp-podw-tiret": "2TIR",
    "potr-tiret": "3TIR",
    "poczw-tiret": "4TIR",
    "piec-tiret": "5TIR",
    "punkt-OTJ": "PKT_OTJ",
    "podpunkt-OTJ": "PPKT_OTJ",
    "nie-ztp-podpunkt-OTJ": "PPKT_OTJ",
    "punkt-odnosnik": "PKT_ODNOŚNIKA",
    "litera-odnosnik": "LIT_ODNOŚNIKA",
    "tiret-odnosnik": "TIR_ODNOŚNIKA",
    "punkt-zarzut": "PKT",
    "punkt-tenoru": "PKT",
    "punkt-postanowienia-dodatkowego": "PKT",
}

COMMON_PART_STYLES = {
    "czesc-wspolna-punkt": "CZ_WSP_PKT",
    "nie-ztp-czesc-wspolna-punkt": "CZ_WSP_PKT",
    "czesc-wspolna-litera": "CZ_WSP_LIT",
    "nie-ztp-czesc-wspolna-litera": "CZ_WSP_LIT",
    "czesc-wspolna-tiret": "CZ_WSP_TIR",
    "nie-ztp-czesc-wspolna-tiret": "CZ_WSP_TIR",
    "czesc-wspolna-podw-tiret": "CZ_WSP_2TIR",
    "nie-ztp-czesc-wspolna-podw-tiret": "CZ_WSP_2TIR",
    "czesc-wspolna-potr-tiret": "CZ_WSP_3TIR",
    "czesc-wspolna-poczw-tiret": "CZ_WSP_4TIR",
    "czesc-wspolna-piec-tiret": "CZ_WSP_5TIR",
    "czesc-wspolna-podpunkt-OTJ": "CZ_WSP_PPKT_OTJ",
    "nie-ztp-czesc-wspolna-podpunkt-OTJ": "CZ_WSP_PPKT_OTJ",
    "czesc-wspolna-punkt-odnosnik": "CZ_WSP_PKT_ODNOŚNIKA",
    "czesc-wspolna-litera-odnosnik": "CZ_WSP_LIT_ODNOŚNIKA",
    "czesc-wspolna-tiret-odnosnik": "CZ_WSP_TIR_ODNOŚNIKA",
}

# The role a unit plays - what the accessible layout needs to know about
# it.
UNIT_ROLES = {
    "ART(§)": "art",
    "UST(§)": "ust",
    "PKT_OTJ": "pkt",
    "PPKT_OTJ": "lit",
}

BOLD_MARKERS = {
    "artykul",
    "artykul-kodeksu",
    "artykul-tj",
    "artykul-kodeksu-tj",
    "nie-ztp-artykul",
    "paragraf",
    "paragraf-tj",
    "nie-ztp-paragraf-rozporzadzenia",
}

# Implicit units: no marker, their content belongs to the enclosing
# unit.
TRANSPARENT_UNITS = {
    "ustep-n",
    "paragraf-kodeksu-n",
    "nie-ztp-ustep-n",
    "nie-ztp-paragraf-kodeksu-n",
}

# Systematization units: their heading (naglowek-*) and the styles of
# its two lines.
SECTION_STYLES = {
    "czesc": ("CZĘŚĆ(KSIĘGA)", "CZĘŚĆ(KSIĘGA)"),
    "ksiega": ("CZĘŚĆ(KSIĘGA)", "CZĘŚĆ(KSIĘGA)"),
    "tytul-jednostka": ("TYT(DZ)_OZN", "TYT(DZ)_PRZEDM"),
    "tytul": ("TYT(DZ)_OZN", "TYT(DZ)_PRZEDM"),
    "dzial": ("TYT(DZ)_OZN", "TYT(DZ)_PRZEDM"),
    "rozdzial": ("ROZDZ(ODDZ)_OZN", "ROZDZ(ODDZ)_PRZEDM"),
    "oddzial": ("ROZDZ(ODDZ)_OZN", "ROZDZ(ODDZ)_PRZEDM"),
}
SECTION_WRAPPERS = {
    "czesc-n",
    "ksiega-n",
    "tytul-n",
    "tytul-n-jednostka",
    "dzial-n",
    "rozdzial-n",
    "oddzial-n",
}

# Blocks that continue a paragraph's text (kontynuacja-akapitu).
TEXT_BLOCK_STYLES = {
    "sankcja-karna": "S_KARN",
    "slubowanie": "CYT",
    "fragment": "NIEART_TEKST",
    "fragment-odnosnik": "ODNOŚNIK",
    "specjalny": "SPEC",
    "uchylenie-OTJ": "UCHYLENIE_W_TJ",
    "podstawa-prawna": "NIEART_TEKST",
    "wprowadzenie-do-opisu": "LEG_W_MAT(FIZ|CHEM)",
    "tytul-tabeli": "TYT_TABELI",
    "odstep-tabeli": "ODST_TABELI",
    "opis-tabeli": "TEKST_w_TABELI",
}

# The act's header: type, issuer, date, title - its first heading.
ACT_HEADER = (
    "rodzaj-aktu",
    "autor-aktu",
    "data",
    "daty",
    "sygnatura",
    "tytul",
    "tytul-ustawy",
    "tytul-kodeksu",
)

ACT_ELEMENTS = {
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
}

SIGNATURE_ELEMENTS = {
    "organ-wydajacy": "NAZ_ORG_WYD",
    "organ-podpisujacy": "NAZ_ORG_WYD",
    "tekst-w-porozumieniu": 'TEKST"w porozumieniu:"',
    "organ-w-porozumieniu": "NAZ_ORG_W_POROZUMIENIU",
}

# The cover letter of a bill: no act template style, the layout defines
# these.
BILL_COVER_STYLES = {
    "winieta": "PROJ_WINIETA",
    "kadencja": "PROJ_KADENCJA",
    "druk": "PROJ_DRUK",
    "miejsce-i-data": "PROJ_MIEJSCE",
    "adresat-pisma-tytul-i-osoba": "PROJ_ADRESAT",
    "adresat-pisma-stanowisko": "PROJ_ADRESAT",
    "kontynuacja-preambuly": "NIEART_TEKST",
}

# Table cell paragraphs. Most published cells are set in Word's default
# style (KOMORKA: Normalny with the usual space below), column titles in
# the centred table style.
TABLE_CELL_STYLES = {
    "tytul-kolumny": "TEKST_w_TABELI_WYŚRODKOWANY",
    "tekst-centr": "TEKST_w_TABELI_WYŚRODKOWANY",
    "liczba": "LICZBA_w_TABELI",
    "tekst-zwykly": "KOMORKA",
    "tekst-1": "TEKST_1_w_TABELI",
    "tekst-2": "TEKST_2_w_TABELI",
    "tekst-3": "TEKST_3_w_TABELI",
    "wyliczenie-1": "NUM_1_w_TABELI",
    "wyliczenie-2": "NUM_2_w_TABELI",
    "wyliczenie-3": "NUM_3_w_TABELI",
    "wyliczenie-4": "NUM_4_w_TABELI",
    "specjalny": "SPEC",
}
TABLE_SECTIONS = ("tbody", "thead", "tfoot")
BORDER_SIDES = ("top", "bottom", "left", "right")

AMENDMENT_HOSTS = {"LIT": "Z_LIT", "TIR": "Z_TIR", "2TIR": "Z_2TIR"}
QUOTE_PARENTS = {"PKT", "LIT", "TIR", "2TIR"}

INLINE_FUNCTIONS = {
    "b": "pogrubienie",
    "i": "kursywa",
    "sup": "gorny",
    "sub": "dolny",
    "wersaliki": "wersaliki",
    "rozstrzelone": "rozstrzelone",
    "petit": "petit",
}

SAFE_SCHEMES = ("http://", "https://", "mailto:", "ftp://")

MONTHS = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)

_SPACE = r"[ \t\n\r]+"
# No-break spaces as in the published acts: after one-letter words ("w
# ustawie"), after the abbreviations that precede a number ("art. 5",
# "Dz. U.") and between a number and the word after it ("2025 r.", "13
# października").
_NO_BREAK = (
    (re.compile(rf"(?<![\w.])([aiouwzAIOUWZ]){_SPACE}"), "\\1\u00a0"),
    (
        re.compile(
            rf"(?<!\w)((?:[Aa]rt|ust|lit|poz|str|par|Dz)\.|pkt|nr|§){_SPACE}"
        ),
        "\\1\u00a0",
    ),
    (re.compile(rf"(?<=\d){_SPACE}(?=[^\W\d]|[%§])"), "\u00a0"),
)

_STYLE_KEY = re.compile(r'^  "((?:[^"\\]|\\.)*)":', re.MULTILINE)


@cache
def style_names() -> set[str]:
    """The styles the official template knows: style-akapitow.typ."""
    source = (TEMPLATE_DIR / "style-akapitow.typ").read_text(encoding="utf-8")
    return {key.replace('\\"', '"') for key in _STYLE_KEY.findall(source)}


# -- the document model ------------------------------------------------


@dataclass
class Paragraph:
    """One paragraph of the act, in a template style."""

    style: str
    text: Inline = field(default_factory=Inline)
    marker: Inline | None = None
    # the marker of the article this paragraph opens ("Art. 5.")
    article: Inline | None = None
    level: int | None = None  # the article's level in the act's outline
    role: str | None = None
    depth: int = 0
    section: str | None = None
    keep: bool = False  # keep with the next paragraph (it introduces a quote)
    has_note: bool = False  # carries a footnote call

    def code(self, previous: str | None, before_note: bool = False) -> str:
        """The ``#akapit(...)`` call; ``previous``: the style above."""
        return (
            "#"
            + call(
                "akapit",
                self.style,
                oznaczenie=self.marker,
                artykul=self.article,
                poziom=self.level,
                rola=self.role,
                glebokosc=self.depth,
                poprzedni=previous,
                sekcja=self.section,
                z_nastepnym=True if self.keep else None,
                z_przypisem=True if self.has_note else None,
                przed_przypisem=True if before_note else None,
                body=self.text,
            ).source
        )


@dataclass
class Table:
    """A table: its cells (Typst dictionaries) placed on the grid."""

    columns: int
    cells: list[dict[str, object]]
    header_rows: int = 0
    repeat_header: bool = False
    width: Code | None = None
    fixed: list[Code | None] | None = None

    def code(self, previous: str | None) -> str:
        """The ``#tabela(...)`` call; ``previous``: the style above."""
        return (
            "#"
            + call(
                "tabela",
                self.cells,
                kolumny=self.columns,
                naglowek=self.header_rows,
                powtorz=self.repeat_header,
                szerokosc=self.width,
                stale=self.fixed if self.fixed and any(self.fixed) else None,
                poprzedni=previous,
            ).source
        )


# What the walk produces: paragraphs, tables and raw Typst code.
Item: TypeAlias = Paragraph | Table | str


@dataclass(frozen=True)
class Context:
    """Where the walk is: quote, depth, section and heading level."""

    prefix: str | None = None  # "Z", "Z_LIT", ... inside an amendment quote
    # the enclosing PKT/LIT/TIR/2TIR inside a quote
    quoted_parent: str | None = None
    depth: int = 0
    section: str | None = None  # "obwieszczenie": the announcement's own part
    heading: int = 1  # heading level of the act being typeset
    in_note: bool = False
    quoted: bool = False  # inside a quotation (amended or cited text)

    def enter(self, style: str) -> Context:
        """The context one level deeper, inside a unit of ``style``."""
        parent = style if self.prefix and style in QUOTE_PARENTS else None
        return replace(self, depth=self.depth + 1, quoted_parent=parent)


@dataclass
class Lead:
    """A unit's marker, waiting for the paragraph that will carry it."""

    marker: Inline | None
    style: str
    role: str | None
    depth: int
    article: Inline | None = None
    level: int | None = None


class ActTypesetter:
    """Walks one schemaPL document, producing its PDF's Typst code."""

    def __init__(self, root: etree._Element) -> None:
        """Start an empty walk of ``root``."""
        self.root = root
        self.items: list[Item] = []
        self.current: Paragraph | None = None
        self.open_quote: str = ""
        self.note_labels: dict[str, str] = {}
        # label -> the note's symbol ("1", "*")
        self.note_symbols: dict[str, str] = {}
        # notes of an open heading's lines, set after it
        self.heading_notes: list[Code] = []
        # the act's references to its own provisions ("#art_13__pkt_7")
        # and the units they lead to
        self.links = InternalLinks(root)
        self.anchored: set[str] = set()
        # "#naglowek(...)[" not yet closed
        self.open_headings: list[tuple[list[Item], int]] = []

    # -- output --------------------------------------------------------

    def source(self, template: str) -> str:
        """The Typst source: template import, masthead, paragraphs."""
        self.document()
        meta = self.masthead()
        lines = [
            f"#import {string(template)}: *",
            "#show: dokument.with("
            + ", ".join(
                f"{key}: {literal(value)}" for key, value in meta.items()
            )
            + ")",
        ]
        # the template sets no space above it
        lines += self.code(self.items, first="POCZATEK")
        return "\n".join(lines) + "\n"

    def code(self, items: list[Item], first: str | None = None) -> list[str]:
        """The Typst lines of ``items``; ``first``: the style above."""
        lines: list[str] = []
        previous = first
        # paragraphs and tables, in order
        following = [item for item in items if not isinstance(item, str)]
        upcoming = iter([*following[1:], None])
        for item in items:
            if isinstance(item, Paragraph):
                after = next(upcoming)
                lines.append(
                    item.code(
                        previous,
                        before_note=isinstance(after, Paragraph)
                        and after.has_note,
                    )
                )
                previous = item.style
            elif isinstance(item, Table):
                next(upcoming)
                lines.append(item.code(previous))
                previous = None
            else:
                lines.append(item)
                if not item.startswith(
                    (
                        "#naglowek",
                        "]",
                        "#kotwica",
                        "#zakladka",
                        "#przypis-naglowka",
                    )
                ):
                    previous = None
        return lines

    def start(self, paragraph: Paragraph) -> Paragraph:
        """Begin a new paragraph (the previous one is complete)."""
        self.flush()
        # the first line of a quote opens with its quotation mark
        if self.open_quote:
            mark = Inline().text(self.open_quote)
            if paragraph.article is not None:
                paragraph.article = mark.extend(paragraph.article)
            elif paragraph.marker is not None:
                paragraph.marker = mark.extend(paragraph.marker)
            else:
                paragraph.text = mark.extend(paragraph.text)
            self.open_quote = ""
        self.current = paragraph
        return paragraph

    def flush(self) -> None:
        """Close the open paragraph, adding it to the items."""
        if self.current is not None:
            self.items.append(self.current)
            self.current = None

    def raw(self, code: str) -> None:
        """Add raw Typst code, closing the open paragraph first."""
        self.flush()
        closing = code == "]" and bool(self.open_headings)
        if closing:
            self.title_heading(*self.open_headings.pop())
        if code.startswith("#naglowek("):
            self.open_headings.append((self.items, len(self.items)))
        self.items.append(code)
        # the notes of the heading's lines follow it
        if closing and not self.open_headings:
            self.items += ["#" + note.source for note in self.heading_notes]
            self.heading_notes = []

    @staticmethod
    def title_heading(items: list[Item], index: int) -> None:
        """Give a closed heading its bookmark title: its lines' text.

        The title leaves out note calls and notes.
        """
        title = " ".join(
            item.text.plain()
            for item in items[index + 1 :]
            if isinstance(item, Paragraph)
        ).strip()
        heading = items[index]  # the "#naglowek(...)[" code
        if title and isinstance(heading, str):
            items[index] = (
                heading[: -len(")[")] + f", tytul: {string(title)})["
            )

    @contextmanager
    def captured(self) -> Generator[list[Item], None, None]:
        """Collect what the walk produces in the block into a new list.

        The list holds a note or a table cell.
        """
        saved = (self.items, self.current, self.open_quote)
        self.items = []
        self.current = None
        self.open_quote = ""
        out: list[Item] = []
        try:
            yield out
            self.flush()
            out.extend(self.items)
        finally:
            self.items, self.current, self.open_quote = saved

    def text_target(self, ctx: Context) -> Inline:
        """Where running text goes: the open paragraph, or a new one."""
        if self.current is None:
            return self.start(
                Paragraph("Normalny", depth=ctx.depth, section=ctx.section)
            ).text
        return self.current.text

    # -- metadata ------------------------------------------------------

    def act(self) -> etree._Element | None:
        """The act element of the document, or ``None``."""
        return next(
            (
                c
                for c in self.root
                if is_element(c) and element_name(c) in ACT_ELEMENTS
            ),
            None,
        )

    def metadata(self, name: str) -> str:
        """The text of the act's metadata field ``name``, or ""."""
        act = self.act()
        meta = child_named(act, "metadane") if act is not None else None
        found = (
            meta.find(f".//{{{SCHEMAPL}}}{name}") if meta is not None else None
        )
        return (found.text or "").strip() if found is not None else ""

    def masthead(self) -> dict[str, object]:
        """What the journal header shows.

        The journal, place and date, position, and the title.
        """
        act = self.act()
        journal = {"DU": "DU", "MP": "MP"}.get(self.metadata("Wydawnictwo"))
        published = _polish_date(self.metadata("DataOgloszenia"))
        place_date = f"Warszawa, dnia {published}" if published else ""
        position = (
            f"Poz. {self.metadata('Pozycja')}"
            if self.metadata("Pozycja")
            else ""
        )
        if act is not None and element_name(act) in (
            "projekt-ustawy",
            "projekt-kodeksu",
            "autopoprawka",
        ):
            journal = journal or "DU"
            cover = child_named(act, "miejsce-i-data")
            place_date = place_date or (
                plain_text(cover) if cover is not None else ""
            )
            if self.metadata("NumerDruku") and not position:
                position = f"Druk nr {self.metadata('NumerDruku')}"
        return {
            "dziennik": journal,
            "miejsce-data": place_date or None,
            "pozycja": position or None,
            "tytul": self.title(),
            "obwieszczenie": act is not None
            and element_name(act) == "obwieszczenie",
        }

    def title(self) -> str:
        """The document title for the PDF metadata, as in the act."""
        if self.metadata("Tytul"):
            return self.metadata("Tytul")
        act = self.act()
        if act is None:
            return "Akt prawny"
        parts = [
            plain_text(child_named(act, name))
            for name in ("rodzaj-aktu", "autor-aktu", "data", "tytul")
        ]
        return " ".join(part for part in parts if part) or "Akt prawny"

    # -- document structure --------------------------------------------

    def document(self) -> None:
        """Walk the document: its acts and statement of reasons."""
        for child in self.root:
            if not is_element(child) or element_namespace(child) != SCHEMAPL:
                continue
            name = element_name(child)
            if name in ACT_ELEMENTS:
                self.act_body(child, Context())
            elif name == "uzasadnienie":
                self.statement_of_reasons(child, Context())
        self.flush()

    def act_body(self, act: etree._Element, ctx: Context) -> None:
        """One act: its header, text, notes and annexes."""
        announcement = element_name(act) == "obwieszczenie"
        if announcement:
            ctx = replace(ctx, section="obwieszczenie")
        if not any(
            element_name(c) in ACT_HEADER and _has_content(c)
            for c in self.elements(act)
        ):
            # no title: its parts head the outline
            ctx = replace(ctx, heading=ctx.heading - 1)
        header: list[etree._Element] = []
        # the act's unplaced notes: after its text, before its
        # annexes
        notes_due = True
        for child in self.elements(act):
            name = element_name(child)
            if name in ("metadane", "oznaczenie"):
                continue  # the masthead shows the publication data
            if notes_due and (
                name in ACT_ELEMENTS
                or name in ("zalacznik", "uzasadnienie", "attach-ref")
            ):
                self.unplaced_notes(act, ctx)
                notes_due = False
            if name in ACT_HEADER:
                header.append(child)
                continue
            if header:
                self.act_header(header, ctx, announcement)
                header = []
            # the consolidated text announced, as an annex
            if name in ACT_ELEMENTS:
                self.raw("#nowa-strona()")
                self.act_body(
                    child, replace(ctx, section=None, heading=ctx.heading + 1)
                )
            elif name == "zalacznik-do":
                self.paragraph(child, 'TEKST"Załącznik(i) do ..."', ctx)
            elif name in BILL_COVER_STYLES:
                self.paragraph(child, BILL_COVER_STYLES[name], ctx)
                following = sibling_element(child, following=True)
                if (
                    name == "druk"
                    and following is not None
                    and element_name(following) == "nr-druku"
                ):
                    # "Druk nr 2887"
                    current = self.current
                    if current is not None:
                        current.text.text(" " + plain_text(following))
            elif name == "nr-druku":
                previous = sibling_element(child, following=False)
                if previous is None or element_name(previous) != "druk":
                    self.paragraph(child, "PROJ_DRUK", ctx)
            elif (
                name == "preambula"
                or name == "upowaznienie-do-reprezentowania"
            ):
                self.plain_paragraphs(child, "NIEART_TEKST", ctx)
            elif name == "podpisujacy":
                self.bill_signatories(child, ctx)
            elif name in SIGNATURE_ELEMENTS or name == "osoba":
                self.signature(child, ctx)
            elif name == "zalacznik":
                self.annex(child, ctx)
            elif name == "uzasadnienie":
                self.statement_of_reasons(child, ctx)
            elif name == "attach-ref":
                self.attached_text(child, ctx)
            else:
                self.block(child, ctx)
        if header:
            self.act_header(header, ctx, announcement)
        if notes_due:
            self.unplaced_notes(act, ctx)

    def unplaced_notes(self, act: etree._Element, ctx: Context) -> None:
        """<AparatOdnosnikow>: notes with no place in the text.

        They are set as notes under the act's text.
        """
        meta = child_named(act, "metadane")
        apparatus = (
            child_named(meta, "AparatOdnosnikow") if meta is not None else None
        )
        notes: list[etree._Element] = (
            [
                n
                for n in self.elements(apparatus)
                if element_name(n) == "odnosnik"
            ]
            if apparatus is not None
            else []
        )
        if notes:
            entries = [
                (note.get("symbol") or str(number), self.note_body(note, ctx))
                for number, note in enumerate(notes, start=1)
            ]
            self.raw("#" + call("odnosniki-aktu", *entries).source)

    def attached_text(self, element: etree._Element, ctx: Context) -> None:
        """<attach-ref>: the announced consolidated text.

        The announcement publishes it as a separate act.
        """
        kind = ACT_TYPE_LABELS.get(element.get("rodzaj") or "")
        text = Inline().text(
            f"Tekst jednolity ({kind}): " if kind else "Tekst jednolity: "
        )
        href = (element.get("href") or "").strip()
        target = _safe_link(href)
        text.wrap(
            "odeslanie", Inline().text(href), target
        ) if target else text.text(href)
        self.start(
            Paragraph(
                "NIEART_TEKST", text=text, depth=ctx.depth, section=ctx.section
            )
        )

    def act_header(
        self, header: list[etree._Element], ctx: Context, announcement: bool
    ) -> None:
        """Act type, issuer, date and title, as one heading.

        The heading is the act's entry in the outline.
        """
        styles = {
            "rodzaj-aktu": 'TEKST"OBWIESZCZENIE"(NAZWA_ORGANU_WYDAJĄCEGO_OTJ)'
            if announcement
            else "OZN_RODZ_AKTU",
            "autor-aktu": 'TEKST"OBWIESZCZENIE"(NAZWA_ORGANU_WYDAJĄCEGO_OTJ)'
            if announcement
            else "OZN_RODZ_AKTU",
            "data": "DATA_OTJ" if announcement else "DATA_AKTU",
            "daty": "DATA_AKTU",
            "sygnatura": "DATA_AKTU",
            "tytul": "TYTUŁ_OTJ" if announcement else "TYTUŁ_AKTU",
            "tytul-ustawy": "TYTUŁ_AKTU",
            "tytul-kodeksu": "TYTUŁ_AKTU",
        }
        lines = [child for child in header if _has_content(child)]
        if not lines:
            return
        self.raw(f"#naglowek(poziom: {ctx.heading})[")
        for child in lines:
            self.paragraph(
                child,
                styles[element_name(child)],
                replace(ctx, depth=0),
                role="naglowek-aktu",
            )
        self.raw("]")

    def annex(self, annex: etree._Element, ctx: Context) -> None:
        """One annex, on a new page, with its heading."""
        self.raw("#nowa-strona()")
        # its parts nest under its heading
        annex_ctx = replace(ctx, section=None, heading=ctx.heading + 1)
        heading_lines = [
            c
            for c in self.elements(annex)
            if element_name(c) in ("zalacznik-nr", "tytul-zalacznika")
        ]
        for child in self.elements(annex):
            name = element_name(child)
            if name == "zalacznik-do":
                self.paragraph(child, 'TEKST"Załącznik(i) do ..."', annex_ctx)
            elif name == "zalacznik-nr":
                if child is heading_lines[0]:
                    self.raw(f"#naglowek(poziom: {ctx.heading + 1})[")
                number = self.marker(child) or Inline()
                text = (
                    Inline().text("Załącznik nr ").extend(number)
                    if not number.is_empty()
                    else Inline().text("Załącznik")
                )
                self.start(
                    Paragraph(
                        "OZN_ZAŁĄCZNIKA",
                        text=text,
                        role="naglowek-aktu",
                        section=None,
                    )
                )
                # its notes follow <nr> ("Załącznik nr 1⁶⁾")
                for part in self.elements(child):
                    if is_annotation(part):
                        self.inline_element(part, text, annex_ctx)
                if child is heading_lines[-1]:
                    self.raw("]")
            elif name == "tytul-zalacznika":
                if child is heading_lines[0]:
                    self.raw(f"#naglowek(poziom: {ctx.heading + 1})[")
                self.paragraph(
                    child, "TYT_ZAL", annex_ctx, role="naglowek-aktu"
                )
                if child is heading_lines[-1]:
                    self.raw("]")
            # an annex kept as a file: its place on the page
            elif name == "zalacznik-binarny":
                self.start(
                    Paragraph("GRAFIKA_RASTROWA", role="grafika")
                ).text.atom(
                    call(
                        "grafika",
                        "Załącznik",
                        plik=child.get("href") or None,
                        szerokosc=Code("100%"),
                    )
                )
            else:
                self.segment(child, annex_ctx)

    def segment(self, element: etree._Element, ctx: Context) -> None:
        """Free content of an annex segment: units, paragraphs..."""
        if element_name(element) == "segment-zalacznika":
            for child in self.elements(element):
                self.segment(child, ctx)
        else:
            self.block(element, ctx)

    def statement_of_reasons(
        self, element: etree._Element, ctx: Context
    ) -> None:
        """<uzasadnienie>: on a new page, its title and sections."""
        self.raw("#nowa-strona()")
        for child in self.elements(element):
            name = element_name(child)
            if name == "tytul-uzasadnienia":
                self.raw(f"#naglowek(poziom: {max(ctx.heading, 1)})[")
                self.paragraph(child, "TYTUŁ_AKTU", ctx, role="naglowek-aktu")
                self.raw("]")
            elif name == "sekcja-uzasadnienia":
                self.statement_section(child, ctx)
            else:
                self.block(child, ctx)

    def statement_section(self, section: etree._Element, ctx: Context) -> None:
        """One section of the statement of reasons, with its title."""
        for child in self.elements(section):
            name = element_name(child)
            if name == "tytul-sekcji":
                self.raw(f"#naglowek(poziom: {ctx.heading + 1})[")
                self.paragraph(
                    child, "ROZDZ(ODDZ)_PRZEDM", ctx, role="naglowek"
                )
                self.raw("]")
            elif name == "sekcja-uzasadnienia":
                self.statement_section(
                    child, replace(ctx, heading=ctx.heading + 1)
                )
            elif name == "p":
                self.start(
                    Paragraph(
                        "NIEART_TEKST", depth=ctx.depth, section=ctx.section
                    )
                )
                self.run(child, ctx)
            else:
                self.block(child, ctx)

    # -- units ---------------------------------------------------------

    def anchor(self, element: etree._Element) -> None:
        """Mark where a unit the act refers to begins, for its links."""
        eid = (element.get("eId") or "").strip()
        if eid and eid in self.links.eids and eid not in self.anchored:
            self.anchored.add(eid)
            self.raw("#" + call("kotwica", _anchor_name(eid)).source)

    def block(
        self, element: etree._Element, ctx: Context, lead: Lead | None = None
    ) -> None:
        """Any block-level element inside an act or a unit."""
        if element_namespace(element) != SCHEMAPL:
            return  # typography hints, comments, amendment markers
        self.anchor(element)
        name = element_name(element)
        if name in UNIT_STYLES:
            self.unit(element, ctx, lead)
        elif name in COMMON_PART_STYLES:
            self.unit_paragraphs(
                element,
                self.style(COMMON_PART_STYLES[name], ctx),
                ctx,
                None,
                role="czesc-wspolna",
            )
        elif name in SECTION_STYLES:
            self.section_unit(element, ctx)
        elif name in SECTION_WRAPPERS or name in TRANSPARENT_UNITS:
            for child in self.elements(element):
                self.block(child, ctx, lead)
                lead = None
        elif name == "p":
            self.start(
                Paragraph(
                    self.style("NIEART_TEKST", ctx),
                    depth=ctx.depth,
                    section=ctx.section,
                )
            )
            self.run(element, ctx)
        elif name in TEXT_BLOCK_STYLES:
            self.paragraph(
                element, self.style(TEXT_BLOCK_STYLES[name], ctx), ctx
            )
        elif name == "tabela":
            self.table(element, ctx)
        elif name in (
            "wzor-mat",
            "wzor",
            "opis",
            "symbol-txt",
            "symbol-mat",
            "objasnienie",
        ):
            self.formula(element, ctx)
        elif name in ("grafika", "grafika-wektorowa"):
            self.graphic(element, ctx)
        # a row or a cell standing alone (quoted): a small table
        elif name == "tr":
            self.table_rows([(element, self.elements(element))], ctx)
        elif name in ("td", "th"):
            self.table_rows([(None, [element])], ctx)
        elif name in (
            "tresc",
            "naglowek-skladu",
            "naglowek-tenoru",
            "naglowek-postanowienia",
            "podstawa-inicjowania",
            "wynik-narady",
            "poswiadczenie",
            "uwagi",
            "protokolant",
            "sedzia",
        ):
            self.paragraph(element, "NIEART_TEKST", ctx)
        elif _has_own_text(element):
            # anything else holding text (<tekst-zwykly> in an annex):
            # running text, its notes and references inline
            self.paragraph(element, "Normalny", ctx)
        elif element.find(".//*") is not None:
            # anything else: keep its content, never lose text
            for child in self.elements(element):
                self.block(child, ctx)

    def bookmark(self, element: etree._Element, ctx: Context) -> None:
        """The unit's entry in the PDF's bookmarks.

        The bookmarks are a tree of the act's own units, not quoted
        ones.
        """
        if ctx.quoted or ctx.in_note:
            return
        level = ctx.heading + 1 + _section_rank(element) + ctx.depth
        # a layout may show an article's heading
        article = UNIT_STYLES[element_name(element)] == "ART(§)"
        self.raw(
            "#"
            + call(
                "zakladka",
                level,
                _bookmark_title(element),
                artykul=True if article else None,
            ).source
        )

    def unit(
        self, element: etree._Element, ctx: Context, lead: Lead | None = None
    ) -> None:
        """A numbered unit: its paragraphs, marker and subunits."""
        self.anchor(element)
        self.bookmark(element, ctx)
        name = element_name(element)
        base = UNIT_STYLES[name]
        marker = self.marker(element)
        # quoted articles are printed in regular weight
        if name in BOLD_MARKERS and not ctx.quoted:
            marker = Inline().wrap("pogrubienie", marker)
        style = self.style(base, ctx)
        role = UNIT_ROLES.get(base, "punkt")
        # "Art. 5. 1. ..." - the article's marker goes with its first
        # ustęp
        if lead is not None:
            self.unit_paragraphs(
                element,
                lead.style,
                ctx,
                marker,
                role=lead.role,
                base=base,
                article=lead.article,
                level=lead.level,
            )
            return
        self.unit_paragraphs(element, style, ctx, marker, role=role, base=base)

    def unit_paragraphs(
        self,
        element: etree._Element,
        style: str,
        ctx: Context,
        marker: Inline | None,
        *,
        role: str | None,
        base: str | None = None,
        article: Inline | None = None,
        level: int | None = None,
    ) -> None:
        """A unit's own paragraphs, then the units it contains."""
        inner = ctx.enter(base or style.rpartition("/")[2])
        if role == "art" and article is None and marker is not None:
            # an article's marker: an entry of the act's outline, unless
            # quoted
            article, marker = marker, None
            level = (
                None
                if ctx.quoted or ctx.in_note
                else ctx.heading + 1 + _section_rank(element)
            )
        pending = (
            Lead(marker, style, role, ctx.depth, article, level)
            if marker or article
            else None
        )
        first_paragraph = True
        for child in self.elements(element):
            name = element_name(child)
            if name in ("nr", "tytul") or element_namespace(child) != SCHEMAPL:
                if name == "tytul":
                    self.paragraph(
                        child, "ROZDZ(ODDZ)_PRZEDM", ctx, role="tytul-artykulu"
                    )
                continue
            if name == "p":
                if pending is not None:
                    self.start_unit(pending, ctx)
                    pending = None
                elif first_paragraph:
                    self.start(
                        Paragraph(
                            style,
                            role=role,
                            depth=ctx.depth,
                            section=ctx.section,
                        )
                    )
                else:
                    self.start(
                        Paragraph(
                            self.continuation(style, ctx),
                            role=role,
                            depth=ctx.depth,
                            section=ctx.section,
                        )
                    )
                first_paragraph = False
                self.run(child, ctx)
            elif name in TRANSPARENT_UNITS:
                self.anchor(child)
                self.unit_paragraphs(
                    child,
                    style,
                    ctx,
                    pending.marker if pending else None,
                    role=role,
                    base=base,
                    article=pending.article if pending else None,
                    level=pending.level if pending else None,
                )
                pending, first_paragraph = None, False
            elif (
                name in UNIT_STYLES
                and pending is not None
                and pending.marker is None
                and role == "art"
                and UNIT_STYLES[name] == "UST(§)"
            ):
                self.unit(child, inner, pending)
                pending = None
            else:
                # a unit with no text of its own still shows its marker
                if pending is not None:
                    self.start_unit(pending, ctx)
                    pending = None
                self.block(child, inner)
        if pending is not None:
            self.start_unit(pending, ctx)

    def start_unit(self, lead: Lead, ctx: Context) -> Paragraph:
        """The paragraph that opens a unit and carries its marker."""
        return self.start(
            Paragraph(
                lead.style,
                marker=lead.marker,
                article=lead.article,
                level=lead.level,
                role=lead.role,
                depth=ctx.depth,
                section=ctx.section,
            )
        )

    # -- tables --------------------------------------------------------

    def table(self, element: etree._Element, ctx: Context) -> None:
        """<tabela>: its rows as one table, <opis-tabeli> under it."""
        rows: list[etree._Element] = []
        legends: list[etree._Element] = []
        for child in self.elements(element):
            name = element_name(child)
            if name in TABLE_SECTIONS:
                rows += [
                    row
                    for row in self.elements(child)
                    if element_name(row) == "tr"
                ]
            elif name == "tr":
                rows.append(child)
            elif name == "opis-tabeli":
                legends.append(child)
            else:
                self.block(child, ctx)
        self.table_rows(
            [(row, self.elements(row)) for row in rows],
            ctx,
            width=_percent(element.get("width")),
        )
        for legend in legends:
            self.block(legend, ctx)

    def table_rows(
        self,
        rows: list[tuple[etree._Element | None, list[etree._Element]]],
        ctx: Context,
        *,
        width: Code | None = None,
    ) -> None:
        """Place the cells on the grid as HTML does.

        Each cell goes in the first column the rows above left free.
        """
        if not any(cells for _, cells in rows):
            return
        marked = [
            row is not None and _yes(row.get("naglowek")) for row, _ in rows
        ]
        titles = [
            bool(cells) and all(_only_column_titles(cell) for cell in cells)
            for _, cells in rows
        ]
        header_rows = 0
        while header_rows < len(rows) and (
            marked[header_rows] or titles[header_rows]
        ):
            header_rows += 1
        table = Table(
            columns=1,
            cells=[],
            header_rows=header_rows,
            repeat_header=any(marked[:header_rows]),
            width=width,
        )
        fixed: dict[int, Code] = {}
        occupied: set[tuple[int, int]] = set()
        # a quoted table opens in its first cell
        opening, self.open_quote = self.open_quote, ""
        for y, (row, cells) in enumerate(rows):
            keep = row is not None and _yes(row.get("niedzielic"))
            # a header cell cannot reach into the body, nor any cell
            # past the last row
            last_row = header_rows if y < header_rows else len(rows)
            x = 0
            for cell in cells:
                while (x, y) in occupied:
                    x += 1
                colspan = _span(cell.get("colspan"))
                rowspan = min(_span(cell.get("rowspan")), last_row - y)
                occupied.update(
                    (x + i, y + j)
                    for i in range(colspan)
                    for j in range(rowspan)
                )
                width = _percent(cell.get("width"))
                if colspan == 1 and width is not None:
                    fixed.setdefault(x, width)
                content, opening = self.table_cell(
                    cell,
                    ctx,
                    x=x,
                    y=y,
                    colspan=colspan,
                    rowspan=rowspan,
                    header=y < header_rows,
                    keep=keep,
                    opening=opening,
                )
                table.cells.append(content)
                x += colspan
        table.columns = max(x for x, _ in occupied) + 1
        table.fixed = [fixed.get(i) for i in range(table.columns)]
        self.flush()
        self.items.append(table)
        # no cell had a line to open: the text after the table does
        self.open_quote = opening

    def table_cell(
        self,
        cell: etree._Element,
        ctx: Context,
        *,
        x: int,
        y: int,
        colspan: int,
        rowspan: int,
        header: bool,
        keep: bool,
        opening: str = "",
    ) -> tuple[dict[str, object], str]:
        """The cell as a Typst dictionary, and the pending quote mark.

        The mark, if any, is still waiting to open a line.
        """
        cell_ctx = replace(ctx, depth=0, section=None)
        with self.captured() as items:
            self.open_quote = opening
            # leniency: an element standing for its cell
            if element_name(cell) not in ("td", "th"):
                self.cell_content(cell, cell_ctx)
            elif not self.elements(cell) and plain_text(cell):
                self.paragraph(cell, "KOMORKA", cell_ctx, role="komorka")
            else:
                for child in self.elements(cell):
                    self.cell_content(child, cell_ctx)
            opening = self.open_quote
        borders = {}
        for side in BORDER_SIDES:
            style, weight = (
                cell.get(f"border-{side}-style"),
                cell.get(f"border-{side}-width"),
            )
            if style == "none":
                borders[side] = "none"
            elif weight in ("thin", "medium"):
                borders[side] = weight
            elif style == "solid":
                borders[side] = "thin"
        words = re.split(r"[ \t\n\r]+", _typeset(plain_text(cell)) or "")
        return {
            "x": x,
            "y": y,
            "kolumny": colspan,
            "wiersze": rowspan,
            "pion": cell.get("vertical-align")
            or ("middle" if header else "top"),
            "ramki": borders,
            "niedzielic": keep,
            "naglowek": header,
            # what sizes its column: the longest words (narrowest), its
            # lines unbroken (widest)
            "slowa": sorted(words, key=len, reverse=True)[:3],
            "akapity": [
                (item.style, item.text.plain())
                for item in items
                if isinstance(item, Paragraph)
            ],
            "pierwszy": items[0].style
            if items and isinstance(items[0], Paragraph)
            else None,
            "ostatni": items[-1].style
            if items and isinstance(items[-1], Paragraph)
            else None,
            "tresc": Code("[" + "".join(self.code(items)) + "]"),
        }, opening

    def cell_content(self, element: etree._Element, ctx: Context) -> None:
        """Content standing for a table cell, in the cell's style."""
        name = element_name(element)
        if (
            element_namespace(element) == SCHEMAPL
            and name in TABLE_CELL_STYLES
        ):
            self.paragraph(
                element,
                self.style(TABLE_CELL_STYLES[name], ctx),
                ctx,
                role="komorka",
            )
        else:
            self.block(element, ctx)

    # -- formulas and graphics -----------------------------------------

    def formula(self, element: etree._Element, ctx: Context) -> None:
        """<wzor-mat>: the formula on its own line, then its legend.

        Each part may also stand alone (quoted in an amendment).
        """
        name = element_name(element)
        if name == "wzor-mat":
            for child in self.elements(element):
                self.block(child, ctx)
        elif name == "wzor":
            math = element.find(f"{{{MATHML}}}math")
            if math is not None:
                self.start(
                    Paragraph(
                        self.style("W_MAT(FIZ|CHEM)", ctx),
                        role="wzor",
                        depth=ctx.depth,
                        section=ctx.section,
                    )
                ).text.atom(self.math(math, display=True))
        elif name == "opis":
            self.legend(element, ctx)
        elif name in ("symbol-txt", "symbol-mat"):
            self.start(
                Paragraph(
                    self.style("LEG_W_MAT(FIZ|CHEM)", ctx),
                    marker=self.symbol(element, ctx),
                    role="legenda",
                    depth=ctx.depth,
                    section=ctx.section,
                )
            )
        else:  # objasnienie
            self.start(
                Paragraph(
                    self.style("LEG_W_MAT(FIZ|CHEM)", ctx),
                    role="legenda",
                    depth=ctx.depth,
                    section=ctx.section,
                )
            )
            self.explanation(element, ctx)

    def legend(self, element: etree._Element, ctx: Context) -> None:
        """<opis>: the symbol, a dash and the explanation in a column.

        For example "Cs", a dash, then "cenę skorygowaną ...".
        """
        symbol = next(
            (
                c
                for c in self.elements(element)
                if element_name(c) in ("symbol-txt", "symbol-mat")
            ),
            None,
        )
        self.start(
            Paragraph(
                self.style("LEG_W_MAT(FIZ|CHEM)", ctx),
                marker=self.symbol(symbol, ctx)
                if symbol is not None
                else None,
                role="legenda",
                depth=ctx.depth,
                section=ctx.section,
            )
        )
        explanation = child_named(element, "objasnienie")
        if explanation is not None:
            self.explanation(explanation, ctx)

    def symbol(self, element: etree._Element, ctx: Context) -> Inline:
        """The symbol of a legend line: text or a formula."""
        if element_name(element) == "symbol-mat":
            math = element.find(f"{{{MATHML}}}math")
            return (
                Inline().atom(self.math(math))
                if math is not None
                else Inline()
            )
        return self.inline(element, ctx)

    def explanation(self, element: etree._Element, ctx: Context) -> None:
        """<objasnienie>: the explanation of a legend line.

        Its first paragraph continues the line; more paragraphs follow
        it.
        """
        if not self.elements(element):
            self.run(element, ctx)
            return
        first = True
        for child in self.elements(element):
            if element_name(child) == "p":
                if not first:
                    self.start(
                        Paragraph(
                            self.style("LEG_W_MAT(FIZ|CHEM)", ctx),
                            role="legenda",
                            depth=ctx.depth,
                            section=ctx.section,
                        )
                    )
                self.run(child, ctx)
                first = False
            else:
                self.block(child, ctx)

    def math(self, math: etree._Element, *, display: bool = False) -> Code:
        """A MathML formula: Typst math, spoken form as alt text."""
        return call(
            "wzor",
            spoken(math),
            Code("$" + typst_math(math) + "$"),
            wyswietlany=True if display else None,
        )

    def graphic(self, element: etree._Element, ctx: Context) -> None:
        """A picture: <grafika> or <grafika-wektorowa>, centred.

        Its caption goes under it. Vector graphics are drawn from the
        SVG in the XML; a picture kept in a separate file keeps its
        place on the page.
        """
        vector = element_name(element) == "grafika-wektorowa"
        caption = child_named(element, "opis-grafiki")
        alt = (
            (element.get("alt") or "").strip()
            or (plain_text(caption) if caption is not None else "")
            or "Grafika"
        )
        svg = next(
            (
                c
                for c in element
                if is_element(c) and element_namespace(c) == SVG
            ),
            None,
        )
        size = {
            "szerokosc": _length(element.get("width")),
            "wysokosc": _length(element.get("height")),
        }
        if svg is not None:
            code = call(
                "grafika",
                alt,
                svg=etree.tostring(svg, encoding="unicode", with_tail=False),
                **size,
            )
        else:
            code = call(
                "grafika",
                alt,
                plik=element.get("href") or element.get("skrot") or None,
                podpisana=True if caption is not None else None,
                **size,
            )
        style = self.style(
            "GRAFIKA_WEKTOROWA" if vector else "GRAFIKA_RASTROWA", ctx
        )
        self.start(
            Paragraph(
                style, role="grafika", depth=ctx.depth, section=ctx.section
            )
        ).text.atom(code)
        if caption is not None:
            self.paragraph(caption, "OPIS_GRAFIKI", ctx)

    def continuation(self, style: str, ctx: Context) -> str:
        """The style of a unit's second and later paragraphs."""
        if style.rpartition("/")[2] in ("ART(§)", "UST(§)", "NIEART_TEKST"):
            return self.style("ZDANIE_NAST_NOWY_WIERSZ", ctx)
        return style

    def section_unit(self, element: etree._Element, ctx: Context) -> None:
        """Chapter, division...: the two-line heading, then content."""
        name = element_name(element)
        mark_style, title_style = (
            self.style(s, ctx) for s in SECTION_STYLES[name]
        )
        level = ctx.heading + 1 + _section_rank(element)
        for child in self.elements(element):
            child_name = element_name(child)
            if child_name.startswith("naglowek-"):
                word = HEADING_WORDS.get(child_name[len("naglowek-") :], "")
                number = self.marker(child)
                mark = (
                    Inline().text(f"{word} ").extend(number)
                    if word
                    else number
                )
                # a quoted chapter is amended text
                heading = not ctx.quoted and not ctx.in_note
                if heading:
                    self.raw(f"#naglowek(poziom: {level})[")
                self.start(
                    Paragraph(
                        mark_style,
                        text=mark,
                        role="naglowek",
                        depth=ctx.depth,
                        section=ctx.section,
                    )
                )
                # the title's lines (<p>, <specjalny>...); a note's call
                # goes on the line before it ("Rozdział 3⁵⁾")
                for part in self.elements(child):
                    if is_annotation(part):
                        self.inline_element(part, self.text_target(ctx), ctx)
                        continue
                    if (
                        element_name(part) == "nr"
                        or element_namespace(part) != SCHEMAPL
                    ):
                        continue
                    self.start(
                        Paragraph(
                            title_style,
                            role="naglowek",
                            depth=ctx.depth,
                            section=ctx.section,
                        )
                    )
                    self.run(part, ctx)
                if heading:
                    self.raw("]")
            elif child_name == "tytul" and name in ("ksiega", "ksiega-n"):
                self.section_unit(child, ctx)
            elif child_name != "nr":
                self.block(child, replace(ctx, heading=ctx.heading))

    def style(self, base: str, ctx: Context) -> str:
        """The template style for a ``base`` paragraph in this context.

        Amended text quoted inside a unit takes the "Z…/" family: the
        prefix names the unit quoting it (Z/ article or point, Z_LIT/
        letter, Z_TIR/ tiret, ZZ/ a quote inside a quote) and "_w_PKT"
        names the quoted unit it sits in.
        """
        if not ctx.prefix:
            return base
        names = style_names()
        candidates = []
        if ctx.quoted_parent:
            candidates.append(f"{ctx.prefix}/{base}_w_{ctx.quoted_parent}")
        candidates += [f"{ctx.prefix}/{base}", f"Z/{base}"]
        return next((name for name in candidates if name in names), base)

    def marker(self, element: etree._Element) -> Inline:
        """The unit's marker ("1)", "Art. 5.", "§ 2¹.").

        It includes the footnote calls from its <nr>.
        """
        name = element_name(element)
        number = ""
        nr = child_named(element, "nr")
        if nr is not None:
            number = number_text(nr)
        template = UNIT_MARKERS.get(name)
        text = template(number) if template else number
        marker = Inline()
        for piece, superscript in superscript_parts(text):
            if superscript:
                marker.wrap("gorny", Inline().text(piece))
            else:
                marker.text(piece)
        if nr is not None:
            for child in nr:
                if (
                    is_element(child)
                    and is_annotation(child)
                    and element_namespace(child) == SCHEMAPL
                ):
                    self.inline_element(child, marker, Context())
        return marker

    # -- paragraphs and running text -----------------------------------

    def paragraph(
        self,
        element: etree._Element,
        style: str,
        ctx: Context,
        *,
        role: str | None = None,
    ) -> None:
        """One paragraph holding the element's running text."""
        self.start(
            Paragraph(style, role=role, depth=ctx.depth, section=ctx.section)
        )
        self.run(element, ctx)

    def plain_paragraphs(
        self, element: etree._Element, style: str, ctx: Context
    ) -> None:
        """A container of <p> paragraphs (preamble...), in one style."""
        paragraphs = [
            c for c in self.elements(element) if element_name(c) == "p"
        ]
        if not paragraphs:
            self.block(element, ctx)
        for p in paragraphs:
            self.start(Paragraph(style, depth=ctx.depth, section=ctx.section))
            self.run(p, ctx)

    def run(self, element: etree._Element, ctx: Context) -> None:
        """The element's text and inline children, in order.

        They go into the open paragraph.
        """
        if element.text:
            self.text_target(ctx).text(_typeset(element.text))
        for child in element:
            if is_element(child):
                self.child_in_text(child, ctx)
            if child.tail:
                self.text_target(ctx).text(_typeset(child.tail))

    def child_in_text(self, child: etree._Element, ctx: Context) -> None:
        """One child of running text: a quote, text or inline part."""
        name = element_name(child)
        namespace = element_namespace(child)
        if namespace == SCHEMAPL and name in (
            "cytat-strukt",
            "tresc-strukt",
            "cytat-blok",
        ):
            self.quote(child, ctx)
        elif namespace == SCHEMAPL and name in ("zdanie", "tekst"):
            self.run(child, ctx)
        elif (
            namespace == AMENDMENT_NS
            and name == "zastap"
            and child.find("*") is not None
        ):
            for grandchild in self.elements(child):
                self.block(grandchild, ctx)
        elif (namespace == SCHEMAPL and name in TEXT_BLOCK_STYLES) or name in (
            "tabela",
            "grafika",
            "grafika-wektorowa",
            "wzor-mat",
        ):
            self.block(child, ctx)
        else:
            self.inline_element(child, self.text_target(ctx), ctx)

    def quote(self, element: etree._Element, ctx: Context) -> None:
        """Quoted units: their own paragraphs, quotation marks included.

        The marks go on the first and the last line.
        """
        opening, closing = quote_marks(element)
        if element_name(element) == "tresc-strukt":
            # a structured citation (an oath, provisions left out of a
            # TJ): plain styles
            quote_ctx = replace(ctx, quoted=True)
        else:
            host = self.host_style(element)
            prefix = (
                "ZZ"
                if ctx.prefix
                else AMENDMENT_HOSTS.get(host, "Z")
                if host is not None
                else "Z"
            )
            quote_ctx = replace(
                ctx, prefix=prefix, quoted_parent=None, quoted=True
            )
        if self.current is not None:
            self.current.keep = (
                True  # the line introducing a quote stays with it
            )
        self.flush()
        self.open_quote = opening
        for child in self.elements(element):
            self.block(child, quote_ctx)
        if self.open_quote:  # nothing in the quote opened a line
            self.text_target(ctx).text(self.open_quote)
            self.open_quote = ""
        if closing:
            self.text_target(ctx).text(closing)

    def host_style(self, element: etree._Element) -> str | None:
        """The style of the unit a quote stands in (Z/, Z_LIT/, ...)."""
        for ancestor in element.iterancestors():
            name = element_name(ancestor)
            if name in UNIT_STYLES:
                return UNIT_STYLES[name]
        return None

    def inline_element(
        self, element: etree._Element, out: Inline, ctx: Context
    ) -> None:
        """An inline element into ``out``."""
        namespace = element_namespace(element)
        if namespace in (TYPOGRAPHY_NS, COMMENTS_NS, AMENDMENT_NS):
            # print hints, editorial comments, amendment markers: not
            # printed
            return
        if namespace == MATHML and element_name(element) == "math":
            out.atom(self.math(element))
            return
        if namespace != SCHEMAPL:
            out.text(plain_text(element))
            return
        name = element_name(element)
        if name in INLINE_FUNCTIONS:
            out.wrap(INLINE_FUNCTIONS[name], self.inline(element, ctx))
        elif name in ("ref", "rref"):
            href = (element.get("href") or element.get("from") or "").strip()
            eid = self.links.target(href, element)
            target = (
                Code(f"label({string(_anchor_name(eid))})")
                if eid
                else _safe_link(href)
            )
            inner = self.inline(element, ctx)
            if target:
                out.wrap("odeslanie", inner, target)
            else:
                out.extend(inner)
        elif name == "h":
            uri = (element.text or "").strip()
            target = _safe_link(uri)
            out.wrap(
                "odeslanie", Inline().text(uri), target
            ) if target else out.text(uri)
        elif name == "odnosnik":
            self.footnote(element, out, ctx)
        elif name == "odsylacz-do-odnosnika":
            label = self.note_labels.get(element.get("id-odnosnika") or "")
            if label:
                out.atom(
                    call(
                        "odsylacz", label, symbol=self.note_symbols.get(label)
                    )
                )
            else:
                out.wrap(
                    "gorny",
                    Inline().text(
                        (
                            element.get("symbol")
                            or element.get("id-odnosnika")
                            or ""
                        )
                        + ")"
                    ),
                )
        elif name == "osoba":
            out.text(person_name(element))
        elif name == "pole":
            value = (
                plain_text(element)
                or field_value(element)
                or element.get("data")
                or ""
            )
            out.text(value)
        elif name == "cytat-w-tekscie":
            opening, closing = quote_marks(element)
            out.text(opening).extend(self.inline(element, ctx)).text(closing)
        elif name in ("zdanie", "tekst"):
            out.extend(self.inline(element, ctx))
        else:
            # definicja-legalna, skrot, mref, odeslanie-tytul, ...:
            # their text as printed
            out.extend(self.inline(element, ctx))

    def inline(self, element: etree._Element, ctx: Context) -> Inline:
        """The element's own running text as a separate run."""
        out = Inline().text(_typeset(element.text))
        for child in element:
            if is_element(child):
                self.inline_element(child, out, ctx)
            out.text(_typeset(child.tail))
        return out

    def footnote(
        self, element: etree._Element, out: Inline, ctx: Context
    ) -> None:
        """An <odnosnik>: a footnote marked with the act's own symbol.

        In a heading only its call stands: Typst does not divide a
        heading between pages, and a note longer than the page's rest
        would carry the heading away from it - the note itself follows
        the heading.
        """
        symbol = (
            element.get("symbol")
            or element.get("id-odnosnika")
            or str(len(self.note_labels) + 1)
        )
        if ctx.in_note:  # a note inside a note: keep it in the text
            out.text(f" [{symbol}) ").extend(self.inline(element, ctx)).text(
                "]"
            )
            return
        label = f"odn-{len(self.note_labels) + 1}"
        self.note_labels[element.get("id-odnosnika") or label] = label
        self.note_symbols[label] = symbol
        if self.current is not None:
            self.current.has_note = True
        body = self.note_body(element, ctx)
        if self.open_headings:
            out.atom(call("odsylacz", label, symbol=symbol))
            self.heading_notes.append(
                call("przypis-naglowka", symbol, label, body=body)
            )
        else:
            out.atom(call("przypis", symbol, label, body=body))

    def note_body(self, element: etree._Element, _ctx: Context) -> Code:
        """The note's paragraphs: the first flows after its marker.

        The other paragraphs are blocks.
        """
        note_ctx = Context(in_note=True)
        with self.captured() as items:
            for child in self.elements(element):
                name = element_name(child)
                if name == "p" and not self.items and self.current is None:
                    self.start(Paragraph("ODNOŚNIK", role="przypis"))
                    self.run(child, note_ctx)
                elif name == "p":
                    self.start(
                        Paragraph(
                            "ZDANIE_NAST_NOWY_WIERSZ_ODNOŚNIKA", role="przypis"
                        )
                    )
                    self.run(child, note_ctx)
                else:
                    self.block(child, note_ctx)
        if not items:
            return Code("[]")
        first = items[0]
        if isinstance(first, Paragraph):
            # the first paragraph flows on after the note's marker
            parts = [first.text.markup(), *self.code(items[1:])]
        else:
            parts = self.code(items)
        return Code("[" + "".join(parts) + "]")

    # -- signatures ----------------------------------------------------

    def signature(self, element: etree._Element, ctx: Context) -> None:
        """A signature: an organ and the person signing.

        For example 'Prezydent Rzeczypospolitej Polskiej: K. Nawrocki'.
        """
        name = element_name(element)
        if name == "osoba":
            previous = sibling_element(element, following=False)
            if (
                previous is not None
                and element_name(previous) in SIGNATURE_ELEMENTS
                and self.current is not None
                and self.current.style
                == SIGNATURE_ELEMENTS[element_name(previous)]
            ):
                if not self.current.text.plain().rstrip().endswith(":"):
                    self.current.text.text(": ")
                else:
                    self.current.text.text(" ")
                self.current.text.wrap(
                    "kursywa", Inline().text(person_name(element))
                )
                return
            paragraph = self.start(
                Paragraph("NAZ_ORG_WYD", role="podpis", section=ctx.section)
            )
            paragraph.text.wrap("kursywa", Inline().text(person_name(element)))
            return
        self.paragraph(element, SIGNATURE_ELEMENTS[name], ctx, role="podpis")

    def bill_signatories(self, element: etree._Element, ctx: Context) -> None:
        """The deputies signing a bill: one name per line."""
        people = [
            c for c in self.elements(element) if element_name(c) == "osoba"
        ]
        if not people:
            self.paragraph(element, "NAZ_ORG_WYD", ctx, role="podpis")
        for person in people:
            self.start(
                Paragraph(
                    "PROJ_PODPISUJACY",
                    text=Inline().text(person_name(person)),
                    role="podpis",
                )
            )

    # -- helpers -------------------------------------------------------

    @staticmethod
    def elements(element: etree._Element) -> list[etree._Element]:
        """The child elements, without comments."""
        return [child for child in element if is_element(child)]


# How a bookmark names a unit: "Art. 5.", "ust. 1", "pkt 2", "lit. a",
# "tiret 1".
_BOOKMARK_WORDS = {
    "UST(§)": "ust.",
    "PKT": "pkt",
    "PKT_OTJ": "pkt",
    "PPKT_OTJ": "ppkt",
    "PKT_ODNOŚNIKA": "pkt",
    "LIT": "lit.",
    "LIT_ODNOŚNIKA": "lit.",
    "TIR": "tiret",
    "TIR_ODNOŚNIKA": "tiret",
    "2TIR": "podwójne tiret",
    "3TIR": "potrójne tiret",
    "4TIR": "poczwórne tiret",
    "5TIR": "pięciokrotne tiret",
}


def _bookmark_title(element: etree._Element) -> str:
    name = element_name(element)
    number = superscripts_text(number_of(element))
    if not number:  # tirets are not numbered: their place among their siblings
        siblings = [
            s
            for s in element.itersiblings(preceding=True)
            if is_element(s) and element_name(s) == name
        ]
        number = str(len(siblings) + 1)
    base = UNIT_STYLES[name]
    if base == "ART(§)":
        return (
            superscripts_text(UNIT_MARKERS[name](number_of(element)))
            if name in UNIT_MARKERS
            else number
        )
    if name in ("paragraf-kodeksu", "nie-ztp-paragraf-kodeksu"):
        return f"§ {number}"
    return f"{_BOOKMARK_WORDS.get(base, 'pkt')} {number}"


def _has_content(element: etree._Element) -> bool:
    """Text or child elements: something to print.

    Amending acts have empty header elements.
    """
    return bool(plain_text(element)) or element.find(".//*") is not None


def _has_own_text(element: etree._Element) -> bool:
    """Text of the element itself, not only of its children.

    Mixed content: "3)<odnosnik>…</odnosnik> bioodpady…".
    """
    return any(
        (text or "").strip()
        for text in (element.text, *(child.tail for child in element))
    )


def _section_rank(element: etree._Element) -> int:
    """How many systematization units with a heading enclose an element.

    Containers without a heading do not count.
    """
    return sum(
        1
        for ancestor in element.iterancestors()
        if element_name(ancestor) in SECTION_STYLES
    )


def _typeset(text: str | None) -> str | None:
    """Document text with the no-break spaces of Polish typesetting."""
    if not text:
        return text
    for pattern, replacement in _NO_BREAK:
        text = pattern.sub(replacement, text)
    return text


def _anchor_name(eid: str) -> str:
    return "jednostka:" + eid


def _yes(value: str | None) -> bool:
    """A yes/no attribute ("tak") that is set."""
    return value is not None and value.strip().lower() not in (
        "",
        "0",
        "false",
        "nie",
    )


def _span(value: str | None) -> int:
    """A colspan/rowspan: a positive number, 1 if missing or invalid."""
    return (
        int(value)
        if value and value.strip().isdigit() and int(value) > 0
        else 1
    )


def _percent(value: str | None) -> Code | None:
    """A width like "40%" as a Typst ratio (none for the full width)."""
    match = re.fullmatch(r"\s*(\d+)%\s*", value or "")
    return (
        Code(f"{match.group(1)}%")
        if match and 0 < int(match.group(1)) < 100
        else None
    )


def _length(value: str | None) -> Code | None:
    """A width or height from the XML as a Typst length.

    The XML writes "100%", "300px" or "5cm".
    """
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*(%|px|pt|mm|cm|in)?\s*", value or ""
    )
    if not match or float(match.group(1)) <= 0:
        return None
    number, unit = match.group(1), match.group(2) or "px"
    if unit == "%":
        return Code(f"{min(float(number), 100):g}%")
    if unit == "px":  # CSS pixels: 96 per inch
        return Code(f"{float(number) * 0.75:g}pt")
    return Code(f"{number}{unit}")


def _only_column_titles(cell: etree._Element) -> bool:
    children = [child for child in cell if is_element(child)]
    return bool(children) and all(
        element_name(child) == "tytul-kolumny" for child in children
    )


def _safe_link(url: str | None) -> str | None:
    """A link target only for ordinary web and mail addresses."""
    value = (url or "").strip()
    return value if value.lower().startswith(SAFE_SCHEMES) else None


def _polish_date(value: str) -> str:
    """Spell out a date: "2026-01-12" -> "12 stycznia 2026 r."."""
    try:
        day = date.fromisoformat(value.strip())
    except ValueError:
        return ""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year} r."


# variant -> template, the PDF standards its file meets, the template's
# inputs
TEMPLATES: dict[str, tuple[str, tuple[str, ...], dict[str, str]]] = {
    "official": ("dziennik.typ", (), {}),
    "accessible": ("dziennik.typ", ("ua-1",), {"uklad": "dostepny"}),
}


def typst_source(
    root: etree._Element, variant: str
) -> tuple[str, tuple[str, ...], dict[str, str]]:
    """The act's PDF as Typst code, with the standards and inputs.

    The PDF standards it must meet and the template's inputs.
    """
    template, standards, inputs = TEMPLATES[variant]
    return ActTypesetter(root).source(template), standards, inputs


def handles(root: etree._Element) -> bool:
    """True for schemaPL documents: the only ones it can typeset."""
    return etree.QName(root).namespace == SCHEMAPL
