"""Test the PDF layouts: notes, mastheads and large print.

The template is checked by querying what Typst laid out: an element in
content Typst drops is never located, and ``here().position()`` tells
where a line stands.
"""

import json
from typing import Any

import pytest
import typst
from lxml import etree
from pytest_mock import MockerFixture

from schemapl_visualizer import PdfError, convert_bytes
from schemapl_visualizer.parsing import parse_xml
from schemapl_visualizer.pdf.typst import TEMPLATE_DIR, compile_pdf
from schemapl_visualizer.profiles import select_pdf_profile

NBSP = "\u00a0"


def _note(number: int, text: str, extra: str = "") -> str:
    """An <odnosnik> with one sentence, then ``extra`` blocks."""
    return (
        f'<odnosnik id-odnosnika="{number}" symbol="{number}">'
        f"<p><zdanie>{text}</zdanie></p>{extra}</odnosnik>"
    )


TITLE_NOTE = _note(
    1,
    "Rozporządzenie służy stosowaniu:",
    "<punkt-odnosnik><nr>1</nr>"
    "<p><zdanie>dyrektywy pierwszej;</zdanie></p></punkt-odnosnik>",
)
ROWS = "".join(
    f"<tr><td><liczba>{i}</liczba></td>"
    f"<td><tekst-zwykly>Pozycja {i}</tekst-zwykly></td></tr>"
    for i in range(1, 41)
)

# An act whose title, chapter heading, annex number and annex title
# carry notes, an annex line of plain text with a note inside it, and a
# table under the annex heading.
ACT = f"""<?xml version="1.0" encoding="UTF-8"?>
<akt-prawny
    xmlns="https://projects.task.gda.pl/caise/NLP/kisi/rcl/schemaPL/1.0">
  <rozporzadzenie>
    <metadane>
      <Wydawnictwo>DU</Wydawnictwo>
      <Pozycja>1</Pozycja>
      <DataOgloszenia>2025-05-05</DataOgloszenia>
    </metadane>
    <rodzaj-aktu>Rozporządzenie</rodzaj-aktu>
    <tytul>w sprawie próby{TITLE_NOTE}</tytul>
    <rozdzial>
      <naglowek-rozdzialu>
        <nr>1</nr>{_note(2, "Rozdział dodany.")}
        <p>Przepisy ogólne</p>
        <specjalny>i wyróżnione</specjalny>
      </naglowek-rozdzialu>
      <paragraf><nr>1</nr><ustep-n><p>Treść.</p></ustep-n></paragraf>
    </rozdzial>
    <zalacznik>
      <zalacznik-nr>
        <nr>1</nr>{_note(3, "W brzmieniu ustalonym.")}
      </zalacznik-nr>
      <tytul-zalacznika>Wykaz{_note(5, "Wykaz dodany.")}</tytul-zalacznika>
      <segment-zalacznika>
        <tekst-zwykly>3){_note(4, "Pozycja dodana.")} bioodpady
z gospodarstw</tekst-zwykly>
        <tabela><tbody>{ROWS}</tbody></tabela>
      </segment-zalacznika>
    </zalacznik>
  </rozporzadzenie>
</akt-prawny>
""".encode()

# Page width less the right margin (A4, 51 pt margins).
RIGHT_EDGE = 595.28 - 51

PREAMBLE = '#import "dziennik.typ": *\n'


def _official_source() -> str:
    root = parse_xml(ACT)
    profile = select_pdf_profile(root)
    assert profile is not None
    source, _, _ = profile.typst_source(root, "official")
    return source


def _query(
    source: str, label: str, *, accessible: bool = False
) -> list[dict[str, Any]]:
    """What Typst laid out under ``<label>``, as JSON values."""
    found = typst.query(
        source.encode(),
        f"<{label}>",
        root=str(TEMPLATE_DIR),  # type: ignore[bad-argument-type] - the stub types root as the input (bytes), typst-py takes a path
        sys_inputs={"uklad": "dostepny"} if accessible else {},
    )
    return json.loads(found)


def _points(length: str) -> float:
    """A length Typst reports ("419.26pt") in points."""
    return float(length.removesuffix("pt"))


def _mark(label: str) -> str:
    """Typst code marking where it stands with ``<label>``."""
    return f"#context [#metadata(here().position())<{label}>]"


def test_annex_number_note_is_shown_in_html() -> None:
    """Renders the note of the annex number ("Załącznik nr 1³⁾")."""
    page = convert_bytes(ACT, source_name="akt.xml").text

    assert "W brzmieniu ustalonym." in page


def test_annex_number_carries_its_note() -> None:
    """Sets the annex number's note after its heading."""
    source = _official_source()

    assert '#przypis-naglowka("3", ' in source
    # a one-letter word keeps to the next one
    assert f"W{NBSP}brzmieniu ustalonym." in source


def test_chapter_heading_carries_its_note_and_lines() -> None:
    """Calls the note on the chapter's number and keeps every line."""
    source = _official_source()

    assert '#"Rozdział "#"1"#odsylacz(' in source
    assert '#przypis-naglowka("2", ' in source
    assert f"i{NBSP}wyróżnione" in source


def test_plain_text_keeps_the_text_after_a_note() -> None:
    """Sets an annex line with a note inside as one paragraph."""
    source = _official_source()

    assert '#przypis("4", ' in source
    assert f'" bioodpady z{NBSP}gospodarstw"' in source


@pytest.mark.parametrize("output_format", ["pdf", "pdf-accessible"])
def test_heading_note_before_a_table(output_format: str) -> None:
    """Typesets, and tags, a table under a heading with a note."""
    result = convert_bytes(
        ACT, source_name="akt.xml", output_format=output_format
    )

    assert result.content.startswith(b"%PDF-")


@pytest.mark.parametrize("accessible", [False, True])
def test_note_points_are_typeset(accessible: bool) -> None:
    """Lays out the points of a note, not only its first paragraph."""
    source = (
        PREAMBLE
        + '#show: dokument.with(dziennik: "DU")\n'
        + '#akapit("Normalny")[Tekst#przypis("1", "odn-1")[#"Wstęp:"'
        + '#akapit("PKT_ODNOŚNIKA", oznaczenie: [1)])'
        + '[#"punkt"#metadata("punkt")<punkt>]]]\n'
    )

    assert len(_query(source, "punkt", accessible=accessible)) == 1


def test_heading_note_is_typeset() -> None:
    """Lays out a heading's note in full while leaving out its call."""
    source = (
        PREAMBLE
        + '#show: dokument.with(dziennik: "DU")\n'
        + '#akapit("Normalny")[Tytuł#odsylacz("odn-1", symbol: "1")]\n'
        + '#przypis-naglowka("1", "odn-1")[#"Wstęp:"'
        + '#akapit("PKT_ODNOŚNIKA", oznaczenie: [1)])'
        + '[#"punkt"#metadata("punkt")<punkt>]]\n'
    )

    assert len(_query(source, "punkt")) == 1


def test_large_print_breaks_a_line_of_dots() -> None:
    """Breaks a dotted line to fill in rather than run off the page."""
    source = (
        PREAMBLE
        + '#show: dokument.with(dziennik: "DU")\n'
        + '#akapit("Normalny")[#"Za rok '
        + "…" * 120
        + '"'
        + _mark("koniec")
        + "]\n"
    )

    (end,) = _query(source, "koniec", accessible=True)

    assert _points(end["value"]["x"]) <= RIGHT_EDGE


def test_large_print_parts_words_held_together_in_a_cell() -> None:
    """Lets a narrow cell divide a chain of non-breaking spaces."""
    chain = "\\u{a0}".join(
        ["poz.", "986", "i", "1871", "oraz", "z", "2025", "r.", "poz.", "620"]
    )

    def cell(x: int, content: str) -> str:
        return (
            f'(x: {x}, y: 0, kolumny: 1, wiersze: 1, pion: "top", '
            "ramki: (:), niedzielic: false, naglowek: false, slowa: (), "
            "akapity: (), pierwszy: none, ostatni: none, "
            f"tresc: [{content}])"
        )

    source = (
        PREAMBLE
        + '#show: dokument.with(dziennik: "DU")\n'
        + "#tabela(kolumny: 2, stale: (0.7, 0.3), ("
        + cell(0, '#"a"')
        + ", "
        + cell(1, f'{_mark("poczatek")}#"{chain}"{_mark("koniec")}')
        + "))\n"
    )

    (start,) = _query(source, "poczatek", accessible=True)
    (end,) = _query(source, "koniec", accessible=True)

    # the chain runs on over several 18 pt lines (unbroken, it overflows
    # its one line and only the mark after it moves down)
    start_y, end_y = _points(start["value"]["y"]), _points(end["value"]["y"])
    assert end_y - start_y > 2 * 18


def test_monitor_polski_text_starts_below_its_masthead() -> None:
    """Starts the text 34.2 pt lower than in Dziennik Ustaw.

    Monitor Polski prints its title in two lines, as published.
    """

    def text_start(journal: str) -> float:
        source = (
            PREAMBLE
            + f'#show: dokument.with(dziennik: "{journal}", '
            + 'miejsce-data: "Warszawa, dnia 5 maja 2025 r.", '
            + 'pozycja: "Poz. 1")\n'
            + f'#akapit("Normalny")[{_mark("start")}#"Tekst"]\n'
        )
        (start,) = _query(source, "start")
        return _points(start["value"]["y"])

    assert text_start("MP") - text_start("DU") == pytest.approx(34.2, abs=0.05)


@pytest.mark.parametrize("output_format", ["pdf", "pdf-accessible"])
def test_act_in_monitor_polski(output_format: str) -> None:
    """Typesets an act under the Monitor Polski masthead."""
    root = etree.fromstring(ACT)
    namespace = etree.QName(root).namespace
    journal = root.find(f".//{{{namespace}}}Wydawnictwo")
    assert journal is not None
    journal.text = "MP"

    result = convert_bytes(
        etree.tostring(root),
        source_name="akt.xml",
        output_format=output_format,
    )

    assert result.content.startswith(b"%PDF-")


def test_typst_failure_sets_notes_in_headings(mocker: MockerFixture) -> None:
    """Typesets again, the notes in the headings, when Typst fails."""
    compile_mock = mocker.patch(
        "schemapl_visualizer.conversion.compile_pdf",
        side_effect=[PdfError("internal error: parent group"), b"%PDF-"],
    )

    result = convert_bytes(
        ACT, source_name="akt.xml", output_format="pdf-accessible"
    )

    assert result.content == b"%PDF-"
    first, second = (call.args[0] for call in compile_mock.call_args_list)
    assert "#przypis-naglowka(" in first
    assert "#przypis-naglowka(" not in second
    assert '#"Rozdział "#"1"#przypis("2", ' in second


def test_other_typst_errors_are_raised(mocker: MockerFixture) -> None:
    """Reports an error of the document itself without retrying."""
    compile_mock = mocker.patch(
        "schemapl_visualizer.conversion.compile_pdf",
        side_effect=PdfError("PDF/UA-1 error: missing document title"),
    )

    with pytest.raises(PdfError):
        convert_bytes(
            ACT, source_name="akt.xml", output_format="pdf-accessible"
        )
    assert compile_mock.call_count == 1


@pytest.mark.parametrize("variant", ["official", "accessible"])
def test_notes_in_headings_are_typeset(variant: str) -> None:
    """Typesets, and tags, the act with its notes in the headings."""
    root = parse_xml(ACT)
    profile = select_pdf_profile(root)
    assert profile is not None
    source, standards, inputs = profile.typst_source(
        root, variant, notes_in_headings=True
    )

    pdf = compile_pdf(source, standards=standards, inputs=inputs)

    assert pdf.startswith(b"%PDF-")
