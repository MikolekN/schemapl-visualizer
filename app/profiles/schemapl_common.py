"""
schemaPL knowledge shared by every output format (HTML, PDF).

Namespaces, unit markers, numbering conventions, addresses (eId) and the
readable descriptions of amendments — everything here works on the XML alone
and knows nothing about how a format draws it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime

from lxml import etree

from ..namespaces import display_label, element_name, element_namespace, is_element

SCHEMAPL = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/schemaPL/1.0"
AMENDMENT_NS = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/schemaPL/now"
TYPOGRAPHY_NS = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/typografia/1.0"
COMMENTS_NS = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/komentarze/1.0"
GUID_NS = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/GUIDs/1.0"
CATEGORY_NS = "https://projects.task.gda.pl/caise/NLP/kisi/rcl/ktg/1.0"
MATHML = "http://www.w3.org/1998/Math/MathML"
SVG = "http://www.w3.org/2000/svg"
XMLDSIG = "http://www.w3.org/2000/09/xmldsig#"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XML = "http://www.w3.org/XML/1998/namespace"

DISPLAY_PREFIXES = {
    SCHEMAPL: "",
    MATHML: "mml",
    SVG: "svg",
    AMENDMENT_NS: "now",
    TYPOGRAPHY_NS: "tpg",
    COMMENTS_NS: "kmn",
    GUID_NS: "gd",
    CATEGORY_NS: "ktg",
    XMLDSIG: "dsig",
    XSI: "xsi",
    XML: "xml",
}

UNIT_MARKERS: dict[str, Callable[[str], str]] = {
    "artykul": lambda number: f"Art. {number}.",
    "artykul-kodeksu": lambda number: f"Art. {number}.",
    "artykul-tj": lambda number: f"Art. {number}.",
    "artykul-kodeksu-tj": lambda number: f"Art. {number}.",
    "nie-ztp-artykul": lambda number: f"Art. {number}.",
    "paragraf": lambda number: f"§ {number}.",
    "paragraf-tj": lambda number: f"§ {number}.",
    "nie-ztp-paragraf-rozporzadzenia": lambda number: f"§ {number}.",
    "paragraf-kodeksu": lambda number: f"§ {number}.",
    "nie-ztp-paragraf-kodeksu": lambda number: f"§ {number}.",
    "ustep": lambda number: f"{number}.",
    "nie-ztp-ustep": lambda number: f"{number}.",
    "punkt": lambda number: f"{number})",
    "nie-ztp-punkt": lambda number: f"{number})",
    "punkt-odnosnik": lambda number: f"{number})",
    "punkt-OTJ": lambda number: f"{number}." if number else "",  # the number is optional
    "podpunkt-OTJ": lambda number: f"{number})",
    "nie-ztp-podpunkt-OTJ": lambda number: f"{number})",
    "punkt-zarzut": lambda number: f"{number})",
    "punkt-postanowienia-dodatkowego": lambda number: f"{number})",
    "punkt-tenoru": lambda number: f"{number}.",
    "litera": lambda number: f"{number})",
    "nie-ztp-litera": lambda number: f"{number})",
    "litera-odnosnik": lambda number: f"{number})",
    "tiret": lambda number: "–",
    "nie-ztp-tiret": lambda number: "–",
    "tiret-odnosnik": lambda number: "–",
    "podw-tiret": lambda number: "– –",
    "nie-ztp-podw-tiret": lambda number: "– –",
    "potr-tiret": lambda number: "– – –",
    "poczw-tiret": lambda number: "– – – –",
    "piec-tiret": lambda number: "– – – – –",
}

SECTION_UNITS = {"ksiega", "czesc", "dzial", "rozdzial", "oddzial", "tytul-jednostka"}

HEADING_WORDS = {
    "ksiegi": "Księga",
    "czesci": "Część",
    "tytulu": "Tytuł",
    "dzialu": "Dział",
    "oddzialu": "Oddział",
    "rozdzialu": "Rozdział",
}

TYPOGRAPHY_HINTS = {"akapit", "typografia"}

FOOTNOTE_NAMES = {"odnosnik", "odsylacz-do-odnosnika"}

def number_of(element: etree._Element) -> str:
    """The number from the element's direct ``<nr>`` child, or ""."""
    for child in element:
        if is_element(child) and element_name(child) == "nr":
            return number_text(child)
    return ""

def is_annotation(node: etree._Element) -> bool:
    """Footnotes and editorial comments: shown apart from the text they sit in."""
    return element_name(node) in FOOTNOTE_NAMES or element_namespace(node) == COMMENTS_NS

def number_text(nr: etree._Element) -> str:
    """The number as plain text.

    In consolidated texts (TJ) ``<nr>`` is mixed content: the number may sit in
    a ``<b>`` and carry footnote markers or comments. Those are excluded here
    (they are rendered separately by ``_nr_annotations``), everything else is text.
    """
    parts: list[str] = [nr.text or ""]
    for child in nr:
        if is_element(child) and not is_annotation(child):
            parts.append("".join(child.itertext()))
        parts.append(child.tail or "")
    return "".join(parts).strip()

_SUPERSCRIPT_INDEX = re.compile(r"\[([^\]]+)\]|%5B(.+?)%5D", re.IGNORECASE)

_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

def _index_of(match: re.Match[str]) -> str:
    return match.group(1) if match.group(1) is not None else match.group(2)

def superscript_parts(text: str) -> list[tuple[str, bool]]:
    """Split a unit number into (text, is_superscript) pieces: the schema writes 2¹ as "2[1]"."""
    parts, last = [], 0
    for match in _SUPERSCRIPT_INDEX.finditer(text):
        parts.append((text[last : match.start()], False))
        parts.append((_index_of(match), True))
        last = match.end()
    parts.append((text[last:], False))
    return [(piece, sup) for piece, sup in parts if piece]

def superscripts_text(text: str) -> str:
    """The same for plain text (outline, tooltips): "2[1]" -> "2¹", "2[1a]" -> "2^1a"."""
    def replace(match: re.Match[str]) -> str:
        index = _index_of(match)
        return index.translate(_SUPERSCRIPT_DIGITS) if index.isdigit() else f"^{index}"
    return _SUPERSCRIPT_INDEX.sub(replace, text)

def plain_text(element: etree._Element | None) -> str:
    """The element's visible text, skipping footnotes and comments, whitespace-collapsed."""
    if element is None:
        return ""
    parts = [element.text or ""]
    for child in element:
        if is_element(child) and not is_annotation(child):
            parts.append(plain_text(child))
        parts.append(child.tail or "")
    return " ".join("".join(parts).split())

def child_named(element: etree._Element, name: str) -> etree._Element | None:
    for child in element:
        if is_element(child) and element_name(child) == name:
            return child
    return None

def sibling_element(element: etree._Element, *, following: bool) -> etree._Element | None:
    """The nearest sibling element after (or before) this one, skipping comments."""
    sibling = element.getnext() if following else element.getprevious()
    while sibling is not None and not is_element(sibling):
        sibling = sibling.getnext() if following else sibling.getprevious()
    return sibling

def section_outline(element: etree._Element) -> tuple[str, str]:
    """(marker, title) for a systematization unit, read from its naglowek-*."""
    for child in element:
        if is_element(child) and element_name(child).startswith("naglowek-"):
            suffix = element_name(child)[len("naglowek-") :]
            word = HEADING_WORDS.get(suffix, "")
            marker = superscripts_text(f"{word} {number_of(child)}".strip())
            title_parts = [child.text or ""]
            for sub in child:
                if is_element(sub) and element_name(sub) not in ("nr", "akapit"):
                    title_parts.append(plain_text(sub))
                title_parts.append(sub.tail or "")
            return marker, " ".join("".join(title_parts).split())
    return "", ""

def person_name(element: etree._Element) -> str:
    """The name of an <osoba>: its imie/nazwisko parts, spaced even when written tight."""
    pieces = [element.text or ""]
    for child in element:
        if is_element(child):
            pieces.append(" " + "".join(child.itertext()) + " ")
        pieces.append(child.tail or "")
    return " ".join("".join(pieces).split())

_QUOTE_MARKS = {"otwierajacy": ("„", ""), "zamykajacy": ("", "”"), "oba": ("„", "”")}

def quote_marks(element: etree._Element) -> tuple[str, str]:
    """Opening/closing quotes according to the cudzyslowy attribute (brak/otwierajacy/...)."""
    return _QUOTE_MARKS.get(element.get("cudzyslowy") or "", ("", ""))

_EID_LABELS = {
    "art": "art.",
    "ust": "ust.",
    "par": "§",
    "pkt": "pkt",
    "ppkt": "ppkt",
    "lit": "lit.",
    "tir": "tiret",
    "odn": "odnośnik",
    "zal": "załącznik",
    "roz": "rozdział",
    "rozdz": "rozdział",
    "dzial": "dział",
    "czesc": "część",
    "ksiega": "księga",
    "oddzial": "oddział",
    "tytul": "tytuł",
    "tab": "tabela",
    "zd": "zdanie",
}

def format_eid(eid: str) -> str:
    """A readable unit address, e.g. "DU/2025/350__art_4__pkt_20" -> "art. 4 pkt 20".

    The leading act segment is dropped: the context names the act.
    """
    parts = []
    for segment in eid.lstrip("#").split("__"):
        if "/" in segment:  # the act, e.g. DU/2025/350
            continue
        if segment == "czw":
            parts.append("część wspólna")
            continue
        kind, _, number = segment.partition("_")
        label = _EID_LABELS.get(kind)
        number = superscripts_text(number.replace("_", " "))
        parts.append(f"{label} {number}" if label and number else segment)
    return " ".join(part for part in parts if part).strip()

_QUOTE_FUNCTION_PHRASES = {
    "dodaj-w": "dodanie w",
    "dodaj-po": "dodanie po",
    "zastap": "nowe brzmienie",
    "dodaj-po-tekscie": "dodanie po tekście w",
    "zastap-tekst": "zastąpienie tekstu w",
    "uchyl-tekst": "uchylenie tekstu w",
    "dodaj-recznie": "dodanie (ręczne) w",
    "zastap-recznie": "zastąpienie (ręczne) w",
    "uchyl-recznie": "uchylenie (ręczne) w",
    "cytuj": "przytoczenie",
}

_INSTRUCTION_PHRASES = {
    "uchyl": "uchylenie",
    "uchyl-akt": "uchylenie aktu",
    "dodaj-po": "dodanie po",
    "dodaj-ustep": "dodanie ustępu w",
    "dodaj-paragraf": "dodanie paragrafu w",
    "usun-ustep": "usunięcie ustępu w",
    "zastap": "zastąpienie",
    "zastap-numer": "zmiana numeru",
    "zamien-tekst": "zamiana tekstu w",
}

_OCCURRENCE_WORDS = {"pierwsze", "drugie", "trzecie", "ostatnie"}

def _occurrence_note(value: str | None) -> str:
    """Which occurrences of the text the instruction touches: a word or numbers ("1; 2; 4")."""
    if not value or value == "wszystkie":
        return ""
    if value in _OCCURRENCE_WORDS:
        return f" ({value} wystąpienie)"
    numbers = [number.strip() for number in value.split(";") if number.strip()]
    if not numbers:
        return ""
    if len(numbers) == 1:
        return f" (wystąpienie nr {numbers[0]})"
    return f" (wystąpienia nr {', '.join(numbers)})"

def amendment_label(element: etree._Element) -> str:
    """A readable one-line description of the amendment, e.g. "dodanie po art. 7"."""
    funkcja = element.get("funkcja")
    if funkcja is not None:
        phrase = _QUOTE_FUNCTION_PHRASES.get(funkcja, funkcja)
    else:
        phrase = _INSTRUCTION_PHRASES.get(element_name(element), display_label(element, DISPLAY_PREFIXES))
    target = format_eid(element.get("element-eId") or "")
    end = format_eid(element.get("element-do-eId") or "")
    if end:
        target = f"{target} – {end}" if target else end
    if target:
        label = f"{phrase} {target}"
    else:  # no eId: the target, if any, is given by GUID (gd:GUIDcelu)
        label = phrase.removesuffix(" w").removesuffix(" po")
        if element.get(f"{{{GUID_NS}}}GUIDcelu"):
            label += " (cel wskazany przez GUID)"
    occurrence = element.get(f"{{{AMENDMENT_NS}}}wystapienie") or element.get("wystapienie")
    return label + _occurrence_note(occurrence)

# Where a reference to the act's own provisions cannot lead: units quoted from
# another act, notes, metadata.
_NOT_TARGETS = {"cytat-strukt", "cytat-blok", "tresc-strukt", "cytat-w-tekscie", "odnosnik", "metadane"}


class InternalLinks:
    """Where the act's references to its own provisions ("#art_13__pkt_7") lead.

    A fragment names a unit without its act's prefix: in the act DU/2026/26,
    "#art_13__pkt_7" is the unit "DU/2026/26__art_13__pkt_7". A document may
    hold more than one act (an announcement and the consolidated text it
    publishes): a reference leads into the act it stands in, else to the first
    unit the fragment names. Units quoted from other acts are never targets.
    """

    def __init__(self, root: etree._Element) -> None:
        self.eids: set[str] = set()  # the units the document's references lead to
        self._units: set[str] = set()
        self._by_fragment: dict[str, str] = {}
        refs = [element for element in root.iter() if is_element(element) and element_name(element) in ("ref", "rref")
                and (element.get("href") or element.get("from") or "").strip().startswith("#")]
        if not refs:
            return
        for element in root.iter():
            eid = (element.get("eId") or "").strip() if is_element(element) else ""
            if not eid or any(element_name(a) in _NOT_TARGETS for a in element.iterancestors()):
                continue
            self._units.add(eid)
            prefix, separator, rest = eid.partition("__")
            for fragment in (eid, rest) if separator and "/" in prefix else (eid,):
                self._by_fragment.setdefault(fragment, eid)
        for ref in refs:
            eid = self.target(ref.get("href") or ref.get("from"), ref)
            if eid:
                self.eids.add(eid)

    def target(self, href: str | None, element: etree._Element) -> str | None:
        """The eId a reference ("#art_13__pkt_7", in ``element``) leads to, or None."""
        value = (href or "").strip()
        if not value.startswith("#") or len(value) < 2:
            return None
        fragment = value[1:]
        prefix = _act_prefix(element)
        if prefix and f"{prefix}__{fragment}" in self._units:
            return f"{prefix}__{fragment}"
        return self._by_fragment.get(fragment)


def _act_prefix(element: etree._Element) -> str:
    """The prefix of the act an element stands in ("DU/2026/26"), from the nearest eId that has one."""
    for node in (element, *element.iterancestors()):
        eid = (node.get("eId") or "").strip()
        prefix = eid.partition("__")[0]
        if "/" in prefix:
            return prefix
    return ""


# Act types (RodzajAktuTyp), as words.
ACT_TYPE_LABELS = {
    "KONSTYTUCJA": "konstytucja",
    "USTAWA": "ustawa",
    "USTAWA_BUDZ": "ustawa budżetowa",
    "ROZP": "rozporządzenie",
    "ZARZĄD": "zarządzenie",
    "ZARZĄD_PORZ": "zarządzenie porządkowe",
    "ZARZĄD_ZAST": "zarządzenie zastępcze",
    "UCHW": "uchwała",
    "UCH_BUDZ": "uchwała budżetowa",
    "POST": "postanowienie",
    "DECYZJA": "decyzja",
    "WYROK": "wyrok",
    "OBW": "obwieszczenie",
    "OBW_TJ": "obwieszczenie — tekst jednolity",
    "OBW_SPROST": "obwieszczenie — sprostowanie",
    "OSW_RZ": "oświadczenie rządowe",
    "OGLOSZ": "ogłoszenie",
    "KOMUN": "komunikat",
    "PROT": "protokół",
    "UMOWA": "umowa",
    "POROZUM": "porozumienie",
    "ANEKS": "aneks",
    "INNY": "inny akt",
    "ARCH": "akt archiwalny (przed 2012 r.)",
    "PROJ_U": "projekt ustawy",
    "PROJ_R": "projekt rozporządzenia",
    "AUTOPOPRAWKA": "autopoprawka",
}


def format_date(value: str) -> str:
    text = value.strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return text

def field_value(element: etree._Element) -> str | None:
    """Resolve the field's @metadane XPath against the act's <metadane> block."""
    xpath = element.get("metadane")
    if not xpath:
        return None
    root = element.getroottree().getroot()
    metadane = root.find(f".//{{{SCHEMAPL}}}metadane")
    if metadane is None:
        return None
    namespaces = {"md": SCHEMAPL, "gd": GUID_NS, "kmn": COMMENTS_NS}
    try:
        values = metadane.xpath(xpath, namespaces=namespaces)
        if not values and "@GUID" in xpath:  # the XPath type still says @GUID; the attribute is gd:GUID now
            values = metadane.xpath(xpath.replace("@GUID", "@gd:GUID"), namespaces=namespaces)
    except etree.XPathError:
        return None
    texts = []
    for value in values:
        text = value if isinstance(value, str) else "".join(value.itertext())
        if text.strip():
            texts.append(text.strip())
    return ", ".join(texts) or None
