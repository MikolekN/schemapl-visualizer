# schemaPL Visualizer

![Standard](https://img.shields.io/badge/readme_style-standard-brightgreen?style=for-the-badge) ![English](https://img.shields.io/badge/selected_language-english-blue?style=for-the-badge) [![Polish](https://img.shields.io/badge/dostępny_język-polski-red?style=for-the-badge)](README.pl.md) ![Python](https://img.shields.io/badge/python_3.11-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

schemaPL Visualizer converts Polish legal acts in schemaPL XML into interactive HTML or PDF (official journal layout or accessible PDF/UA).

It can be used as a FastAPI HTTP service, as the `schemapl-visualizer`
command, or as the `schemapl_visualizer` Python library. The XML is always
the source: HTML and PDF are both made from it, and PDF never goes through
HTML. Before converting, the HTTP service can send the XML to the CAISE
reference extractor, which marks the act's references so that they become
links, and it accepts a DOCX, which the CAISE DOCX → XML converter turns into
XML first.

The outputs are:

- `html` – a self-contained, interactive page: a table of contents,
  collapsible units, footnotes, metadata, formulas, and the result of an
  optional XSD validation;
- `pdf` – the act as published in Dziennik Ustaw / Monitor Polski: the
  paragraph styles of the Word template for acts, Times New Roman, the
  journal's masthead with the emblem, running header and footnotes, links to
  cited acts;
- `pdf-accessible` – the same document made easier to read for visually
  impaired readers: large print (18 pt text, the whole layout scaled with it)
  in a sans-serif face (Atkinson Hyperlegible, drawn for readers with low
  vision; the masthead keeps the journal's face), 1.5 line spacing, text set
  flush left without hyphenation, links underlined, stronger table rules, and
  a tagged PDF/UA-1 file (the title, chapters and annexes as headings,
  footnotes as notes, table headers, alternative texts for formulas and
  pictures).

Both PDFs carry the act's structure as a bookmark tree (the table of contents
a PDF viewer shows): chapters, articles, ustępy, points, letters and tirets,
each leading to its unit. References to the act's own provisions are links to
them.

Documentation: <https://projects.task.gda.pl/caise/caise-documentation/-/wikis/services/usluga_67>

## Table of Contents

- [Install](#install)
  - [Install the Python Library](#install-the-python-library)
  - [Install the HTTP Service](#install-the-http-service)
  - [Set Up a Development Environment](#set-up-a-development-environment)
  - [Dependencies](#dependencies)
- [Usage](#usage)
  - [How to Get Started?](#how-to-get-started)
  - [HTTP Service](#http-service)
  - [Command Line](#command-line)
  - [Python Library](#python-library)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [PDF Output](#pdf-output)
- [Adding Support for Another Schema](#adding-support-for-another-schema)
- [API](#api)
  - [HTTP API](#http-api)
  - [Python API](#python-api)
- [License](#license)

## Install

Requires Python 3.11 or newer. Choose the installation path that matches how
you intend to use the project.

### Install the Python Library

Install the package from the private GitLab Package Registry. Replace
`<token>` with your GitLab token:

```bash
pip install schemapl-visualizer --extra-index-url "https://gitlab-ci-token:<token>@projects.task.gda.pl/api/v4/projects/2941/packages/pypi/simple"
```

This installs the Python library and the `schemapl-visualizer` command.

### Install the HTTP Service

The HTTP service is not part of the package: it runs from `source/api/` in a
checkout, or from the container image. Install its dependencies with the
`service` extra:

```bash
uv sync --locked --no-default-groups --extra service
```

### Set Up a Development Environment

Clone the repository, enter its directory, and synchronize the locked
development environment:

```bash
git clone https://projects.task.gda.pl/caise/services/nlp-lex/rcl/67-wizualizacja-aktow-prawnych.git
cd schemapl-visualizer
uv sync --locked --extra service
```

If uv is unavailable and you only need to run the service from the checkout,
install the exported runtime requirements and the package instead:

```bash
pip install --requirement requirements.txt
pip install --no-deps .
```

After changing dependencies, refresh the pip-compatible runtime export for
environments without uv:

```bash
uv export --locked --extra service --no-default-groups --no-emit-project --no-hashes --format requirements.txt --output-file requirements.txt
```

### Dependencies

The PDF layouts need fonts installed in the system. The container image has
them; elsewhere, install them yourself.

1. Install Times New Roman or Liberation Serif, the face of the official
   layout.
2. Install Cambria Math or TeX Gyre Termes Math, the face of formulas.
3. Install Atkinson Hyperlegible for the accessible version (otherwise
   Verdana, Arial or Liberation Sans is used).

    On Debian or Ubuntu the packages below provide all three. Debian puts the
    math font in the TeX tree, which Typst does not search, so it is copied
    to the system fonts:

    - UNIX:

        ```bash
        sudo apt-get install fonts-liberation fonts-texgyre-math fonts-atkinson-hyperlegible
        sudo cp -r /usr/share/texmf/fonts/opentype/public/tex-gyre-math /usr/share/fonts/opentype/
        ```

    - Windows: Times New Roman and Cambria Math come with the system;
      install Atkinson Hyperlegible from the Braille Institute's website.

## Usage

schemaPL Visualizer can be used as an HTTP service, a command, or a Python
library.

### How to Get Started?

The HTTP service reads its configuration from environment variables, which
tell it how to reach the CAISE reference extractor and DOCX → XML converter.
When the service is run from a checkout, the variables can also come from a
`.env` file in the directory it is started from; variables set in the
environment take precedence. The container image contains no `.env` file:
pass the variables with `--env-file` or `--env`.

| Variable | Default | Description |
| --- | --- | --- |
| `RUN_LOCAL` | `false` | `true`: reach the upstream services over their public routes, which need credentials. `false`: reach them by their internal service names. |
| `SERVICE_USER` | none | User for the upstream services (HTTP Basic). |
| `SERVICE_PASSWORD` | none | Password for the upstream services. |
| `REF_SERVICE_FIELD` | `file` | Form field the reference extractor expects the XML in. |
| `DOCX_SERVICE_FIELD` | `docxFile` | Form field the DOCX → XML converter expects the DOCX in. |
| `LOG_LEVEL` | `INFO` | `DEBUG` adds the request and response headers of upstream calls (the Authorization value stays hidden). |

An `Authorization` header sent by the client is forwarded to the upstream
services and takes precedence over `SERVICE_USER` and `SERVICE_PASSWORD`.
Never commit the `.env` file: it is ignored by Git and Docker.

### HTTP Service

Start the service from the repository root:

```bash
uv run uvicorn main:app --app-dir source/api --host 127.0.0.1 --port 8000
```

The start page at <http://127.0.0.1:8000/> has a single form: a file to drop
or choose (XML or DOCX, told apart by its content), the result as tiles (HTML,
PDF, PDF dostępny, XML), the reference lookup and the XSD validation as
options. The conversion runs on the page: its progress, any error, then the
result to open or download. Without JavaScript the form posts as usual and the
browser shows the result. Swagger UI is available at
<http://127.0.0.1:8000/docs>.

Alternatively, run the service with Docker, passing the configuration as
environment variables:

```bash
docker build --tag schemapl-visualizer:local .
docker run --rm --publish 127.0.0.1:8000:8000 --env-file .env schemapl-visualizer:local
```

Published image:
`containers.projects.task.gda.pl/caise/services/nlp-lex/rcl/67-wizualizacja-aktow-prawnych:latest`

#### Input

A schemaPL act, `akt.xml`.

#### Command

Convert the act to PDF without the reference lookup:

```bash
curl --form "file=@akt.xml" --form "output=pdf" --output akt.pdf http://127.0.0.1:8000/convert/no-refs
```

#### Output

`akt.pdf`, the act in the official journal layout.

### Command Line

#### Input

A schemaPL act, `akt.xml`, or a folder of acts.

#### Command

Convert the act to the accessible PDF; in a development checkout, prefix the
command with `uv run`. `--schema schema.xsd` turns on XSD validation, whose
result the HTML page shows.

```bash
schemapl-visualizer akt.xml --format pdf-accessible --output output
```

#### Output

`output/akt.accessible.pdf`. Each act is written to the output folder under
its own name, with the extension of the format: `.html`, `.pdf` or
`.accessible.pdf`. The command returns 1 when a file could not be converted.

### Python Library

#### Input

A schemaPL act, `akt.xml`.

#### Command

Convert the act to PDF and save it:

```python
from pathlib import Path

from schemapl_visualizer import convert_file

result = convert_file("akt.xml", output_format="pdf")
Path(f"akt.{result.file_extension}").write_bytes(result.content)
```

#### Output

`akt.pdf`, the act in the official journal layout.

The library emits records through Python's standard `logging` package but
does not configure logging itself.

## Testing

Pytest runs the library, command and HTTP API tests; the upstream services are
mocked. With branch coverage, as CI measures it (global threshold 70%):

```bash
uv run pytest --cov --cov-branch
```

Apply Ruff's safe fixes and formatter before committing:

```bash
uv run ruff check --fix .
uv run ruff format .
```

Run the same quality checks used by CI:

```bash
uv run ruff format --check --diff .
uv run ruff check .
uv run pyrefly check
uv audit --locked
```

## Project Structure

```text
schemapl-visualizer/
├── source/                                    # Service and package source code.
│   ├── api/                                   # FastAPI service, not part of the package.
│   │   ├── settings/                          # Environment-based configuration.
│   │   ├── template/                          # Upload page and CAISE logo.
│   │   ├── main.py                            # HTTP endpoints and application.
│   │   ├── upstream.py                        # Calls to other CAISE services.
│   │   ├── refextractor.py                    # Reference extractor client.
│   │   ├── d2xconverter.py                    # DOCX → XML converter client.
│   │   └── logs.py                            # Service log configuration.
│   ├── schemapl_visualizer/                   # The Python package.
│   │   ├── __init__.py                        # Public API.
│   │   ├── __main__.py                        # Runs the command with python -m.
│   │   ├── cli.py                             # The schemapl-visualizer command.
│   │   ├── conversion.py                      # XML → HTML / PDF conversion.
│   │   ├── parsing.py                         # Secure XML parsing.
│   │   ├── validation.py                      # XSD validation.
│   │   ├── namespaces.py                      # Element name helpers.
│   │   ├── html/                              # Rendering engine and page template.
│   │   ├── pdf/                               # Typst, MathML and layout templates.
│   │   └── profiles/                          # Schema profiles and their registry.
│   │       └── schemapl/                      # schemaPL: shared, HTML and PDF code.
│   └── scripts/                               # Maintenance scripts, not packaged.
│       └── paragraph_styles.py                # Regenerates style-akapitow.typ.
├── tests/                                     # Library, command and HTTP API tests.
│   └── data/                                  # Sample schemaPL acts.
├── validation/                                # CAISE service validation.
│   ├── caise/                                 # Validation utilities.
│   ├── tests/                                 # Validation checks.
│   │   ├── h_test.xml                         # Sample act sent by the checks.
│   │   ├── health.py                          # Availability check.
│   │   ├── reproducibility.py                 # Expected-output check.
│   │   └── volume.py                          # Volume check.
│   ├── requirements.txt                       # Validation dependencies.
│   └── run_test.py                            # Validation test runner.
├── .dockerignore                              # Files kept out of the container image.
├── .gitignore                                 # Files kept out of Git.
├── .gitlab-ci.yml                             # Test, quality, publishing and validation jobs.
├── .python-version                            # Python version used by uv.
├── CHANGELOG.md                               # Release history.
├── Dockerfile                                 # Service container definition.
├── LICENSE                                    # GNU AGPL v3.0 license.
├── MANIFEST.in                                # Source distribution contents.
├── NOTICE                                     # License audit.
├── public-info.yaml                           # Service catalog entry.
├── pyproject.toml                             # Package metadata and dependencies.
├── README.md                                  # English documentation.
├── README.pl.md                               # Polish documentation.
├── requirements.txt                           # Pinned runtime dependencies.
└── uv.lock                                    # Locked dependency graph.
```

## PDF Output

`source/schemapl_visualizer/profiles/schemapl/pdf.py` walks the schemaPL
document and writes Typst code: the paragraphs of the act, each with the
paragraph style Word gives it in the publication (`PKT`, `Z_LIT/UST(§)`, ...),
its marker and its place in the structure. The Typst template
`source/schemapl_visualizer/pdf/templates/dziennik.typ` draws them — as
published, or in its accessible version (the template input
`uklad: "dostepny"`) — and [Typst](https://typst.app) compiles the PDF
(`source/schemapl_visualizer/pdf/typst.py`). MathML formulas become Typst math
(`source/schemapl_visualizer/pdf/mathml.py`).

`source/schemapl_visualizer/pdf/templates/style-akapitow.typ` holds the
paragraph styles of the Word template for acts. It is generated from a
publication DOCX:

```bash
uv run python source/scripts/paragraph_styles.py <publication.docx>
```

## Adding Support for Another Schema

1. Copy `source/schemapl_visualizer/profiles/schemapl/` to
   `source/schemapl_visualizer/profiles/<your_schema>/`.
2. Change the namespace URLs and the element handling to match your
   vocabulary. `dispatch(element, state, inline)` in `html.py` returns the
   HTML for an element, or `None` to let the engine fall back.
3. Register it in `source/schemapl_visualizer/profiles/__init__.py`: add its
   `PROFILE` to `_PROFILES` and give it a `root_namespaces` set.

## API

### HTTP API

| Endpoint | Input | Response |
| --- | --- | --- |
| `GET /` | None | HTML upload page |
| `POST /convert/file` | Form: `file` (XML or DOCX), `output` (`html`, `pdf`, `pdf-accessible`, `xml`), `odeslania` (`true` to look up references), `walidacja` (`true` to validate) with `schema_file` (any number of `.xsd` files or a `.zip`) | The result; `xml` returns the intermediate XML as a download |
| `POST /convert` | Form: XML `file`, `output`, optional `schema_file` | The result, with references looked up |
| `POST /convert/no-refs` | Form: XML `file`, `output`, optional `schema_file` | The result, without references |
| `POST /convert/docx` | Form: DOCX `file`, `output` (also `xml`), optional `schema_file` | The result, with references looked up |

Validation runs for HTML only, the one result that shows it. PDF is available
for schemaPL documents; other XML is shown as HTML by a generic view. Errors
are answered with HTTP 400 and a page explaining them.

### Python API

#### Classes

| Name | Description | Key Attributes |
| --- | --- | --- |
| `ConversionResult` | A converted document. | `content`, `media_type`, `file_extension`, `text` |
| `SchemaValidator` | An XML Schema loaded from a file, ready to validate documents. | `path`, `compiled`, `load_error` |
| `ValidationResult` | The outcome of validating one document. | `status`, `errors`, `schema_error`, `validated`, `is_valid` |
| `UnsupportedDocumentError` | Raised for PDF of a document no PDF profile handles. | None |
| `PdfError` | Raised when Typst cannot typeset the document. | None |

#### Functions

| Name | Parameters | Returns | Description |
| --- | --- | --- | --- |
| `convert_file` | `path: Path \| str`, `validator: SchemaValidator \| None`, `output_format: str` | `ConversionResult` | Converts the XML file at `path` into the output format. |
| `convert_bytes` | `data: bytes`, `source_name: str`, `validator: SchemaValidator \| None`, `output_format: str` | `ConversionResult` | Converts XML given as bytes into the output format. |
| `available_formats` | None | `list[str]` | Lists the output formats: `html`, `pdf`, `pdf-accessible`. |
| `load_validator` | `schema_path: Path \| str \| None` | `SchemaValidator \| None` | Loads an XSD, or returns `None` without a path. |

Malformed XML raises `lxml.etree.XMLSyntaxError`.

## License

Copyright © 2024-2026 CAISE project (KPOD.05.10-IW.10-0005/24) / Gdansk University of Technology.

This project is licensed under the [GNU AGPL-3.0-only License](LICENSE).
