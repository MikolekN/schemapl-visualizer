# schemaPL Visualizer

![Standard](https://img.shields.io/badge/styl_readme-standardowy-brightgreen?style=for-the-badge) ![Polski](https://img.shields.io/badge/wybrany_język-polski-red?style=for-the-badge) [![Angielski](https://img.shields.io/badge/available_language-english-blue?style=for-the-badge)](README.md) ![Python](https://img.shields.io/badge/python_3.11-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

schemaPL Visualizer przetwarza akty prawne zapisane w XML zgodnym ze schematem schemaPL na interaktywny HTML lub PDF (w układzie dziennika urzędowego albo dostępny PDF/UA).

Może być używany jako usługa HTTP oparta na FastAPI, jako polecenie
`schemapl-visualizer` lub jako biblioteka Python `schemapl_visualizer`. Źródłem
jest zawsze XML: z niego powstają zarówno HTML, jak i PDF, a PDF nigdy nie
powstaje z HTML. Przed konwersją usługa HTTP może wysłać XML do ekstraktora
odesłań CAISE, który oznacza odesłania aktu, tak że stają się linkami. Usługa
przyjmuje też DOCX, który konwerter DOCX → XML CAISE najpierw zamienia na XML.

Formaty wyniku:

- `html` – samodzielna, interaktywna strona: spis treści, zwijane jednostki,
  przypisy, metadane, wzory oraz wynik opcjonalnej walidacji XSD;
- `pdf` – akt w układzie publikacji w Dzienniku Ustaw / Monitorze Polskim: style
  akapitów szablonu aktu prawnego dla Worda, Times New Roman, nagłówek dziennika z godłem,
  żywa pagina i przypisy, linki do przywoływanych aktów;
- `pdf-accessible` – ten sam dokument w wersji łatwiejszej do czytania dla osób
  niedowidzących: duży druk (tekst 18 pt, cały układ powiększony razem z nim)
  krojem bezszeryfowym (Atkinson Hyperlegible, zaprojektowany dla osób
  słabowidzących; nagłówek dziennika zachowuje krój dziennika), interlinia 1,5,
  tekst wyrównany do lewej bez dzielenia wyrazów, podkreślone linki, wyraźniejsze
  linie tabel oraz otagowany plik PDF/UA-1 (tytuł, rozdziały i załączniki jako
  nagłówki, przypisy jako noty, nagłówki tabel, teksty alternatywne wzorów
  i rysunków).

Oba PDF-y zawierają strukturę aktu jako drzewo zakładek (spis treści widoczny
w przeglądarce PDF): rozdziały, artykuły, ustępy, punkty, litery i tiret, każde
prowadzące do swojej jednostki. Odesłania do przepisów tego samego aktu są
linkami do nich.

Dokumentacja: <https://projects.task.gda.pl/caise/caise-documentation/-/wikis/services/usluga_67>

## Spis treści

- [Instalacja](#instalacja)
  - [Instalacja biblioteki Python](#instalacja-biblioteki-python)
  - [Instalacja usługi HTTP](#instalacja-usługi-http)
  - [Konfiguracja środowiska deweloperskiego](#konfiguracja-środowiska-deweloperskiego)
  - [Fonty](#fonty)
- [Użycie](#użycie)
  - [Usługa HTTP](#usługa-http)
  - [Wiersz poleceń](#wiersz-poleceń)
  - [Biblioteka Python](#biblioteka-python)
- [Konfiguracja](#konfiguracja)
- [Wynik PDF](#wynik-pdf)
- [Testowanie](#testowanie)
- [Struktura projektu](#struktura-projektu)
- [API](#api)
  - [API HTTP](#api-http)
  - [API Python](#api-python)
- [Obsługa innego schematu](#obsługa-innego-schematu)
- [Licencja](#licencja)

## Instalacja

Wymaga Pythona 3.11 lub nowszego. Wybierz sposób instalacji odpowiedni do
planowanego użycia projektu.

### Instalacja biblioteki Python

Zainstaluj pakiet z prywatnego GitLab Package Registry. Zastąp `<token>` swoim
tokenem GitLab:

```bash
pip install schemapl-visualizer --extra-index-url "https://gitlab-ci-token:<token>@projects.task.gda.pl/api/v4/projects/2556/packages/pypi/simple"
```

Instaluje to bibliotekę Python i polecenie `schemapl-visualizer`.

### Instalacja usługi HTTP

Usługa HTTP nie wchodzi w skład pakietu: działa z katalogu `source/api/`
w kopii repozytorium albo z obrazu kontenera. Zainstaluj jej zależności
z dodatkiem `service`:

```bash
uv sync --locked --no-default-groups --extra service
```

### Konfiguracja środowiska deweloperskiego

Sklonuj repozytorium, przejdź do jego katalogu i zsynchronizuj zablokowane
środowisko deweloperskie:

```bash
git clone https://projects.task.gda.pl/caise/services/nlp-lex/schemapl-visualizer.git
cd schemapl-visualizer
uv sync --locked --extra service
```

Jeśli uv jest niedostępne, a potrzebujesz jedynie uruchomić usługę z kopii
repozytorium, zainstaluj wyeksportowane zależności uruchomieniowe i pakiet:

```bash
pip install --requirement requirements.txt
pip install --no-deps .
```

Po zmianie zależności odśwież eksport zgodny z pip dla środowisk bez uv:

```bash
uv export --locked --extra service --no-default-groups --no-emit-project --no-hashes --format requirements.txt --output-file requirements.txt
```

### Fonty

Układy PDF wymagają zainstalowanych fontów (obraz kontenera je zawiera):
Times New Roman lub Liberation Serif, Cambria Math lub TeX Gyre Termes Math,
a dla wersji dostępnej Atkinson Hyperlegible (w przeciwnym razie Verdana, Arial
lub Liberation Sans).

## Użycie

schemaPL Visualizer może być używany jako usługa HTTP, polecenie lub biblioteka
Python.

### Usługa HTTP

Uruchom usługę z katalogu głównego repozytorium:

```console
uv run uvicorn main:app --app-dir source/api --host 127.0.0.1 --port 8000
```

Strona startowa pod adresem <http://127.0.0.1:8000/> ma jeden formularz: plik do
upuszczenia lub wybrania (XML albo DOCX, rozpoznany po zawartości), wynik jako
kafelki (HTML, PDF, PDF dostępny, XML) oraz wyszukiwanie odesłań i walidację
XSD jako opcje. Konwersja odbywa się na stronie: jej postęp, ewentualny błąd,
a potem wynik do otwarcia lub pobrania. Bez JavaScriptu formularz wysyła się
zwyczajnie, a przeglądarka pokazuje wynik. Swagger UI jest dostępny pod adresem
<http://127.0.0.1:8000/docs>.

Usługę można też uruchomić w Dockerze, przekazując
[konfigurację](#konfiguracja) jako zmienne środowiskowe:

```console
docker build --tag schemapl-visualizer:local .
docker run --rm --publish 127.0.0.1:8000:8000 --env-file .env schemapl-visualizer:local
```

Opublikowany obraz:
`containers.projects.task.gda.pl/caise/services/nlp-lex/schemapl-visualizer:latest`

#### Dane wejściowe

Akt w schemacie schemaPL, `akt.xml`.

#### Polecenie

```bash
curl --form "file=@akt.xml" --form "output=pdf" --output akt.pdf http://127.0.0.1:8000/convert/no-refs
```

#### Wynik

`akt.pdf`, akt w układzie dziennika urzędowego.

### Wiersz poleceń

#### Dane wejściowe

Akt w schemacie schemaPL, `akt.xml`, albo katalog aktów.

#### Polecenie

```bash
schemapl-visualizer akt.xml --format pdf-accessible --output output
```

W kopii deweloperskiej poprzedź polecenie `uv run`. `--schema schema.xsd`
włącza walidację XSD, której wynik pokazuje strona HTML.

#### Wynik

`output/akt.accessible.pdf`. Każdy akt trafia do katalogu wyjściowego pod własną
nazwą, z rozszerzeniem formatu: `.html`, `.pdf` lub `.accessible.pdf`. Polecenie
zwraca 1, gdy któregoś pliku nie udało się przetworzyć.

### Biblioteka Python

#### Dane wejściowe

Akt w schemacie schemaPL, `akt.xml`.

#### Polecenie

```python
from pathlib import Path

from schemapl_visualizer import convert_file

result = convert_file("akt.xml", output_format="pdf")
Path(f"akt.{result.file_extension}").write_bytes(result.content)
```

#### Wynik

`akt.pdf`, akt w układzie dziennika urzędowego.

Biblioteka emituje rekordy przez standardowy pakiet `logging` Pythona, ale sama
nie konfiguruje logowania.

## Konfiguracja

Usługa HTTP odczytuje konfigurację ze zmiennych środowiskowych. Uruchomiona
z kopii repozytorium może je też wczytać z pliku `.env` w katalogu, z którego
jest uruchamiana; zmienne ustawione w środowisku mają pierwszeństwo. Obraz
kontenera nie zawiera pliku `.env`: przekaż zmienne przez `--env-file` lub
`--env`.

| Zmienna | Domyślnie | Opis |
| --- | --- | --- |
| `RUN_LOCAL` | `false` | `true`: łączy się z ekstraktorem odesłań i konwerterem DOCX → XML przez ich publiczne adresy, które wymagają poświadczeń. `false`: łączy się z nimi po wewnętrznych nazwach usług. |
| `SERVICE_USER` | brak | Użytkownik usług zewnętrznych (HTTP Basic). |
| `SERVICE_PASSWORD` | brak | Hasło do usług zewnętrznych. |
| `REF_SERVICE_FIELD` | `file` | Pole formularza, w którym ekstraktor odesłań oczekuje XML. |
| `DOCX_SERVICE_FIELD` | `docxFile` | Pole formularza, w którym konwerter DOCX → XML oczekuje DOCX. |
| `LOG_LEVEL` | `INFO` | `DEBUG` dodaje nagłówki żądań i odpowiedzi usług zewnętrznych (wartość Authorization pozostaje ukryta). |

Nagłówek `Authorization` wysłany przez klienta jest przekazywany do usług
zewnętrznych i ma pierwszeństwo przed `SERVICE_USER` i `SERVICE_PASSWORD`.
Nigdy nie commituj pliku `.env`: Git i Docker go pomijają.

## Wynik PDF

`source/schemapl_visualizer/profiles/schemapl/pdf.py` przechodzi dokument
schemaPL i zapisuje kod Typst: akapity aktu, każdy ze stylem akapitu, który
nadaje mu Word w publikacji (`PKT`, `Z_LIT/UST(§)`, ...), z oznaczeniem i miejscem
w strukturze. Szablon Typst
`source/schemapl_visualizer/pdf/templates/dziennik.typ` rysuje je — jak
w publikacji albo w wersji dostępnej (wejście szablonu `uklad: "dostepny"`) —
a [Typst](https://typst.app) kompiluje PDF
(`source/schemapl_visualizer/pdf/typst.py`). Wzory MathML stają się matematyką
Typst (`source/schemapl_visualizer/pdf/mathml.py`).

`source/schemapl_visualizer/pdf/templates/style-akapitow.typ` zawiera style
akapitów szablonu aktu prawnego dla Worda. Jest generowany z DOCX publikacji:

```console
uv run python source/scripts/paragraph_styles.py <publikacja.docx>
```

## Testowanie

Pytest uruchamia testy biblioteki, polecenia i API HTTP z pokryciem gałęzi;
usługi zewnętrzne są zastąpione atrapami. Skonfigurowany globalny próg pokrycia
wynosi 70%:

```console
uv run pytest
```

Przed commitem zastosuj bezpieczne poprawki i formatowanie Ruff:

```console
uv run ruff check --fix .
uv run ruff format .
```

Uruchom te same kontrole jakości co CI:

```console
uv run ruff format --check --diff .
uv run ruff check .
uv run pyrefly check
uv audit --locked
```

Kontrole w `validation/` sprawdzają wdrożoną usługę. Wymagają środowiska
walidacji CAISE i są uruchamiane przez zadania walidacji wdrożenia w CI.

## Struktura projektu

```text
schemapl-visualizer/
├── source/
│   ├── api/                            # Usługa FastAPI, poza pakietem
│   │   ├── settings/                   # Konfiguracja ze zmiennych środowiskowych
│   │   ├── template/                   # Strona przesyłania i logo CAISE
│   │   ├── main.py                     # Endpointy HTTP i aplikacja
│   │   ├── upstream.py                 # Wywołania innych usług CAISE
│   │   ├── refextractor.py             # Klient ekstraktora odesłań
│   │   ├── d2xconverter.py             # Klient konwertera DOCX → XML
│   │   └── logs.py                     # Konfiguracja logów usługi
│   ├── schemapl_visualizer/
│   │   ├── __init__.py                 # Publiczne API
│   │   ├── __main__.py                 # python -m schemapl_visualizer
│   │   ├── cli.py                      # Polecenie schemapl-visualizer
│   │   ├── conversion.py               # XML → HTML / PDF
│   │   ├── parsing.py                  # Bezpieczne parsowanie XML
│   │   ├── validation.py               # Walidacja XSD
│   │   ├── namespaces.py               # Pomocnicze funkcje nazw elementów
│   │   ├── html/                       # Silnik renderowania i szablon strony
│   │   ├── pdf/                        # Typst, MathML i szablony układu
│   │   └── profiles/
│   │       └── schemapl/               # schemaPL: wspólne, HTML i PDF
│   └── scripts/
│       └── paragraph_styles.py         # Generuje style-akapitow.typ
├── tests/                              # Testy biblioteki, polecenia i API HTTP
│   └── data/                           # Przykładowe akty schemaPL
├── validation/                         # Walidacja usługi CAISE
│   ├── caise/                          # Narzędzia walidacji
│   ├── tests/
│   │   ├── h_test.xml                  # Przykładowy akt wysyłany przez kontrole
│   │   ├── health.py                   # Kontrola dostępności
│   │   ├── reproducibility.py          # Kontrola oczekiwanego wyniku
│   │   └── volume.py                   # Kontrola obciążenia
│   ├── requirements.txt                # Zależności walidacji
│   └── run_test.py                     # Uruchamianie testów walidacji
├── .dockerignore
├── .gitignore
├── .gitlab-ci.yml                      # Zadania budowania, publikacji i walidacji
├── .python-version                     # Wersja Pythona używana przez uv
├── CHANGELOG.md                        # Historia wydań
├── Dockerfile                          # Definicja kontenera usługi
├── LICENSE                             # Licencja GNU AGPL v3.0
├── MANIFEST.in                         # Zawartość dystrybucji źródłowej
├── NOTICE                              # Audyt licencji
├── public-info.yaml                    # Wpis w katalogu usług
├── pyproject.toml                      # Metadane pakietu i bezpośrednie zależności
├── README.md                           # Dokumentacja w języku angielskim
├── README.pl.md                        # Dokumentacja w języku polskim
├── requirements.txt                    # Przypięte zależności uruchomieniowe
└── uv.lock                             # Zablokowany graf zależności
```

## API

### API HTTP

| Endpoint | Dane wejściowe | Odpowiedź |
| --- | --- | --- |
| `GET /` | Brak | Strona HTML z formularzem |
| `POST /convert/file` | Formularz: `file` (XML lub DOCX), `output` (`html`, `pdf`, `pdf-accessible`, `xml`), `odeslania` (`true`, aby wyszukać odesłania), `walidacja` (`true`, aby walidować) z `schema_file` (dowolna liczba plików `.xsd` lub `.zip`) | Wynik; `xml` zwraca pośredni XML do pobrania |
| `POST /convert` | Formularz: `file` XML, `output`, opcjonalnie `schema_file` | Wynik z wyszukanymi odesłaniami |
| `POST /convert/no-refs` | Formularz: `file` XML, `output`, opcjonalnie `schema_file` | Wynik bez odesłań |
| `POST /convert/docx` | Formularz: `file` DOCX, `output` (także `xml`), opcjonalnie `schema_file` | Wynik z wyszukanymi odesłaniami |

Walidacja działa tylko dla HTML, jedynego wyniku, który ją pokazuje. PDF jest
dostępny dla dokumentów schemaPL; inny XML jest pokazywany jako HTML w widoku
ogólnym. Błędy są zwracane z kodem HTTP 400 i stroną z wyjaśnieniem.

### API Python

| Interfejs | Zwraca |
| --- | --- |
| `convert_file(path, *, validator=None, output_format="html")` | `ConversionResult` z `content`, `media_type`, `file_extension` |
| `convert_bytes(data, *, source_name, validator=None, output_format="html")` | `ConversionResult` |
| `available_formats()` | `["html", "pdf", "pdf-accessible"]` |
| `load_validator(schema_path)` | `SchemaValidator` albo `None` bez ścieżki |

Konwersja zgłasza `lxml.etree.XMLSyntaxError` dla niepoprawnego XML,
`UnsupportedDocumentError` dla PDF dokumentu, którego nie obsługuje żaden profil PDF,
oraz `PdfError`, gdy Typst nie może złożyć dokumentu.

## Obsługa innego schematu

1. Skopiuj `source/schemapl_visualizer/profiles/schemapl/` do
   `source/schemapl_visualizer/profiles/<twoj_schemat>/`.
2. Zmień adresy przestrzeni nazw i obsługę elementów zgodnie ze swoim
   słownikiem. `dispatch(element, state, inline)` w `html.py` zwraca HTML
   elementu albo `None`, aby silnik użył widoku ogólnego.
3. Zarejestruj go w `source/schemapl_visualizer/profiles/__init__.py`: dodaj jego
   `PROFILE` do `_PROFILES` i nadaj mu zbiór `root_namespaces`.

## Licencja

Copyright © 2026 CAISE.

Projekt na licencji: [GNU AGPL-3.0-only License](LICENSE).
