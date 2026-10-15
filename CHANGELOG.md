Changelog

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.
Format oparty jest na Keep a Changelog,
a wersjonowanie zgodne z Semantic Versioning.

---

[2.0.0] - 2026-10-14
### Dodano
- polecenie `schemapl-visualizer` (także `python -m schemapl_visualizer`) zastępujące `convert.py`
- testy jednostkowe biblioteki, poleceń i usługi HTTP z przykładowymi aktami w `tests/data/`
- walidację wdrożonej usługi CAISE (`health`, `reproducibility`, `volume`) w `validation/`
- logo CAISE i numer wersji na stronie startowej usługi
- pliki `LICENSE`, `NOTICE` (audyt licencji zależności, fontów, danych i obrazów), `MANIFEST.in`, `public-info.yaml` i `README.pl.md`
- test czasu wygenerowania strony HTML z zamrożonym zegarem (freezegun w grupie `test`)
- `HEALTHCHECK` w obrazie kontenera
- strona HTML: wyszukiwanie w treści (bez względu na wielkość liter i polskie znaki, także w zwiniętych jednostkach), tryb ciemny, zmiana wielkości tekstu, podgląd przypisów po najechaniu, pasek postępu czytania, przycisk powrotu na górę, podświetlenie miejsca po przejściu z odesłania lub spisu treści, obsługa zwijania z klawiatury, spis treści i panel informacji o dokumencie do ukrycia (wybór jest zapamiętywany), układ dla telefonów i wydruku
- spis treści strony HTML pokazuje początek treści artykułów bez tytułu, a strona nosi tytuł aktu (z metadanych albo z nagłówka aktu) zamiast nazwy pliku
- panel informacji o dokumencie zaczyna się kartą z rodzajem aktu, adresem publikacyjnym (albo numerem druku), oznaczeniem, czy akt obowiązuje, i odnośnikami do ELI, ISAP i druku sejmowego; metadane są pogrupowane w sekcje (daty, organy, hasła, powiązania, przebieg w czasie, publikacja, identyfikatory), a słowa kluczowe i nazwy własne pokazane jako etykiety

### Zmieniono
- zmieniono nazwę projektu na `schemapl-visualizer`
- przeniesiono repozytorium do nowej przestrzeni: `caise/services/nlp-lex/rcl/schemapl-visualizer`
- strona startowa i dokumentacja API noszą tytuł usługi „Wizualizacja aktów prawnych”
- przeniesiono kod do układu `source/`: pakiet `schemapl_visualizer` (biblioteka i polecenie) oraz usługa HTTP w `source/api/`
- pogrupowano pakiet na `html/`, `pdf/` i `profiles/schemapl/`
- konfigurację usługi (`RUN_LOCAL`, `SERVICE_USER`, `SERVICE_PASSWORD`, `LOG_LEVEL`, `REF_SERVICE_FIELD`, `DOCX_SERVICE_FIELD`) wczytuje pydantic-settings ze zmiennych środowiskowych lub pliku `.env` w katalogu uruchomienia
- wprowadzono uv: `pyproject.toml`, `uv.lock`, grupy zależności `test`, `quality` i `dev` oraz dodatek `service` z zależnościami usługi HTTP
- `requirements.txt` jest eksportowany z `uv.lock`
- obraz kontenera według standardu CI/CD i konteneryzacji: budowany wieloetapowo przez uv, uruchamiany na Docker Hardened Image; fonty PDF kopiowane z etapu budowania razem z ich licencjami
- pipeline CI według standardu: testy, checki jakości, wersja publikacyjna i ręczna publikacja pakietu oraz obrazu
- kod zgodny ze standardem jakości kodu (Ruff, Pyrefly); wyciszenia podają regułę i powód
- wyjątek `UnsupportedDocument` nazywa się `UnsupportedDocumentError`
- adresy usług zewnętrznych inne niż http(s) są odrzucane
- `python main.py` nasłuchuje na 127.0.0.1
- README według standardu README
- `public-info.yaml`: tytuł z numerem usługi, właściciel `caise_platform_admin` i zależności `dependsOn`
- przeniesiono skrypt generujący style akapitów do `source/scripts/paragraph_styles.py`, a tabelę stylów do `style-akapitow.typ`

### Naprawiono
- PDF nie powstawał, gdy przypis zaczynał się tabelą
- w widoku ogólnym strony HTML długie atrybuty zachodziły na panel boczny; szerokie tabele i wzory przewijają się we własnym polu zamiast poszerzać stronę
- strona HTML z kontenera podaje czas wygenerowania w strefie Europe/Warsaw zamiast UTC (`TZ` w obrazie)
- dokument zagnieżdżony głębiej niż 100 poziomów elementów jest odrzucany wyjątkiem `DocumentTooDeepError` (w usłudze HTTP błąd 400) zamiast błędu 500 i wielotysięcznego wpisu w logu; parser znów stosuje ograniczenia libxml2 (bez `huge_tree`)

### Usunięto
- plik `.env.example`; zmienne konfiguracji opisuje README
- przyjmowanie plików DOCX: endpoint `POST /convert/docx` i rozpoznawanie DOCX w `POST /convert/file`; usługa przyjmuje wyłącznie XML

---

[1.1.0] - 2026-10-05
### Zmieniono
- PDF dostępny jest wersją układu dziennika urzędowego (ten sam szablon, nagłówek i style akapitów) w dużym druku, zamiast osobnego układu
- uproszczono interfejs strony startowej

---

[1.0.5] - 2026-10-02
### Dodano
- wynik w PDF: układ Dziennika Ustaw / Monitora Polskiego i PDF dostępny (PDF/UA-1)
- endpoint `POST /convert/file` z jednym formularzem dla XML i DOCX
- endpoint `POST /convert/no-refs` bez wyszukiwania odesłań

### Zmieniono
- dostosowano do zmian schematu schemaPL
- oczekiwanie na wynik ekstraktora odesłań
- rozszerzono logowanie wywołań usług zewnętrznych

---

[1.0.0] - 2026-08-06
### Dodano
- konwersja XML w schemacie schemaPL na HTML
- konwersja DOCX → XML przez usługę zewnętrzną
- wyszukiwanie odesłań przez ekstraktor odesłań
- usługa HTTP i obraz kontenera
