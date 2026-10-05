# XML → HTML / PDF converter

Turns XML schema (schemaPL - Polish legal acts) into readable, self-contained HTML,
or into PDF in two layouts:

- `pdf` – the act as published in Dziennik Ustaw / Monitor Polski: the RCL Word
  template's paragraph styles, Times New Roman, the journal's masthead with the
  emblem, running header and footnotes, links to cited acts;
- `pdf-accessible` – the same document made easier to read for visually impaired
  readers: large print (18 pt text, the whole layout scaled with it) in a
  sans-serif face (Atkinson Hyperlegible, drawn for readers with low vision; the
  masthead keeps the journal's face), 1.5 line spacing, text set flush left
  without hyphenation, links underlined, stronger table rules, and a tagged
  PDF/UA-1 file (the title, chapters and annexes as headings, footnotes as notes,
  table headers, alternative texts for formulas and pictures).

Both PDFs carry the act's structure as a bookmark tree (the table of contents a
PDF viewer shows): chapters, articles, ustępy, points, letters and tirets, each
leading to its unit. References to the act's own provisions are links to them.

The XML is always the source: DOCX is first converted to XML, and HTML and PDF
are both made from the XML (PDF never goes through HTML).

## Running

CLI:

    python convert.py <file-or-folder> [-o OUTPUT] [-f html|pdf|pdf-accessible] [--schema schema.xsd]

WEB:

    uvicorn app.service:app --reload

## Web service

One form, one pipeline:

    XML  ─────────────────┐                     ┌─→ HTML
                          ├─→ (references) ─────┼─→ PDF (official look)
    DOCX ─→ XML ──────────┘                     ├─→ PDF (accessible)
                                                └─→ XML

The start page has a single form: a file to drop or choose (XML or DOCX, told
apart by its content), the result as tiles (HTML, PDF, PDF dostępny, XML), the
reference lookup and the XSD validation as options (validation for the HTML
result only: it is where its result shows). The conversion runs on the page: its
progress, any error, then the result to open or download. Without JavaScript the
form posts as usual and the browser shows the result.

The form posts to `POST /convert/file`: `file`, `output` (`html`, `pdf`,
`pdf-accessible`, `xml`), `odeslania` (`true` to look up references), and
`walidacja` (`true` to validate) with `schema_file` (any number of `.xsd` files or
a `.zip`). Validation runs for HTML only, the one result that shows it. A DOCX is posted to the
converter and its XML continues as if uploaded; `xml` returns the intermediate
XML (with the references found). PDF is available for schemaPL documents.

The earlier endpoints remain for programs: `POST /convert` (XML, with
references), `POST /convert/no-refs` (XML, without) and `POST /convert/docx`
(DOCX, with references), each with `output` and `schema_file`.

## PDF output

`app/profiles/schemapl_pdf.py` walks the schemaPL document and writes Typst code:
the paragraphs of the act, each with the RCL paragraph style Word gives it in the
publication (`PKT`, `Z_LIT/UST(§)`, ...), its marker and its place in the structure.
The Typst template `app/templates/pdf/dziennik.typ` draws them — as published, or
in its accessible version (the template input `uklad: "dostepny"`) — and
[Typst](https://typst.app) compiles the PDF (`app/typst.py`). MathML formulas
become Typst math (`app/mathml.py`).

`app/templates/pdf/rcl-styles.typ` holds the RCL template's paragraph styles. It
is generated from a publication DOCX:

    python scripts/rcl_styles.py <publication.docx>

The PDF layout needs its fonts installed (the Docker image has them): Times New
Roman or Liberation Serif, Cambria Math or TeX Gyre Termes Math, and for the
accessible version Atkinson Hyperlegible (else Verdana, Arial or Liberation Sans).

## Adding support for another schema

1. Copy `app/profiles/schemapl.py` to `app/profiles/<your_schema>.py`.
2. Change the namespace URLs and the element handling to match your vocabulary.
   `dispatch(element, state, inline)` returns the HTML for an element, or `None`
   to let the engine fall back.
3. Register it in `app/profiles/__init__.py`: add its `PROFILE` to `_PROFILES`
   and give it a `root_namespaces` set.
