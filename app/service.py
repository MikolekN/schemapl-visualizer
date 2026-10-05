"""FastAPI web service.

Run with:
    uvicorn app.service:app --reload
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from lxml import etree
from markupsafe import escape

from .conversion import UnsupportedDocument, available_formats, convert_bytes
from .docx import load_docx_service
from .env import load_env_file
from .logs import configure_logging
from .page import render_index
from .refs import load_ref_service
from .typst import PdfError
from .upstream import UpstreamError
from .validation import SchemaUploadError, SchemaValidator, load_validator_from_uploads

_applied_env = load_env_file()
configure_logging()
log = logging.getLogger(__name__)
if _applied_env:
    log.info("wczytano z .env: %s", ", ".join(_applied_env))

_docx_service = load_docx_service()
_ref_service = load_ref_service()
log.info(
    "DOCX → XML: %s (%s), pole %r",
    _docx_service.url,
    _docx_service.describe_auth(),
    _docx_service.field_name,
)
log.info(
    "wyszukiwanie odesłań: %s (%s), pole %r",
    _ref_service.url,
    _ref_service.describe_auth(),
    _ref_service.upstream.field_name,
)

app = FastAPI(title="XML → HTML / PDF")


def _error_response(message: str) -> HTMLResponse:
    log.warning("odpowiedź 400 dla użytkownika: %s", message)
    html = (
        '<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
        "<title>Błąd</title></head><body "
        'style="font-family:sans-serif;max-width:640px;margin:4rem auto;padding:0 1rem">'
        "<h1>Nie udało się przetworzyć dokumentu</h1>"
        f'<p style="color:#b91c1c"><code>{escape(message)}</code></p>'
        '<p><a href="/">&larr; powrót</a></p></body></html>'
    )
    return HTMLResponse(html, status_code=400)


async def _resolve_validator(schema_files: list[UploadFile]) -> SchemaValidator | None:
    """The schema uploaded with this request, or ``None`` — no validation."""
    uploads = [
        (upload.filename, await upload.read()) for upload in schema_files if upload.filename
    ]
    uploads = [(name, data) for name, data in uploads if data]
    if not uploads:
        return None
    return load_validator_from_uploads(uploads)


async def _docx_to_xml(request: Request, data: bytes, filename: str) -> bytes:
    return await run_in_threadpool(
        _docx_service.send,
        data,
        filename=filename,
        authorization=request.headers.get("authorization"),
    )


async def _extract_refs(request: Request, xml: bytes, filename: str) -> bytes:
    started = time.monotonic()
    try:
        result = await run_in_threadpool(
            _ref_service.send,
            xml,
            filename=filename,
            authorization=request.headers.get("authorization"),
        )
    except UpstreamError:
        log.exception("wyszukiwanie odesłań przerwane po %s", _elapsed(started))
        raise
    log.info(
        "wyszukiwanie odesłań zakończone: %d B → %d B w %s",
        len(xml),
        len(result),
        _elapsed(started),
    )
    return result


def _elapsed(started: float) -> str:
    return f"{(time.monotonic() - started) * 1000:.0f} ms"


def _attachment(disposition: str, filename: str) -> dict[str, str]:
    """A Content-Disposition header that keeps a non-ASCII file name.

    The name comes from the upload: control characters (a header cannot carry
    them) go, and the plain-ASCII form has no quote or backslash to break it.
    """
    filename = "".join(ch for ch in filename if ch.isprintable()) or "dokument"
    ascii_name = filename.encode("ascii", "replace").decode("ascii")
    ascii_name = ascii_name.replace("?", "_").replace('"', "_").replace("\\", "_")
    return {"Content-Disposition": f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"}


async def _convert_xml(
    data: bytes, source_name: str, validator: SchemaValidator | None, output: str = "html"
) -> Response:
    if output not in available_formats():
        return _error_response(f"Nieznany format wyniku: {output}")
    if output != "html":
        validator = None  # only the HTML view shows the validation's result
    try:
        result = await run_in_threadpool(
            convert_bytes, data, source_name=source_name, validator=validator, output_format=output
        )
    except etree.XMLSyntaxError as exc:
        return _error_response(f"Niepoprawny XML – {exc}")
    except UnsupportedDocument:
        return _error_response("PDF można utworzyć tylko z dokumentu w schemacie schemaPL.")
    except PdfError as exc:
        return _error_response(f"Nie udało się złożyć PDF – {exc}")
    if result.media_type == "application/pdf":
        # shown in the browser, saved under the act's own name
        name = f"{Path(source_name).stem or 'dokument'}.{result.file_extension}"
        return Response(content=result.content, media_type=result.media_type, headers=_attachment("inline", name))
    return Response(content=result.content, media_type=result.media_type)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        render_index()
    )

@app.post("/convert")
async def convert(
    request: Request,
    file: UploadFile = File(...),
    schema_file: list[UploadFile] = File(default=[]),
    output: str = Form(default="html"),
) -> Response:
    try:
        validator = await _resolve_validator(schema_file)
    except SchemaUploadError as exc:
        return _error_response(f"Nie udało się wczytać schematu – {exc}")

    source_name = file.filename or "dokument.xml"
    data = await file.read()
    try:
        data = await _extract_refs(request, data, source_name)
    except UpstreamError as exc:
        return _error_response(f"Wyszukiwanie odesłań nie powiodło się – {exc}")
    return await _convert_xml(data, source_name, validator, output)

@app.post("/convert/no-refs")
async def convert_no_refs(
    file: UploadFile = File(...),
    schema_file: list[UploadFile] = File(default=[]),
    output: str = Form(default="html"),
) -> Response:
    """Jak ``/convert``, ale bez wyszukiwania odesłań – sam XML → HTML lub PDF."""
    try:
        validator = await _resolve_validator(schema_file)
    except SchemaUploadError as exc:
        return _error_response(f"Nie udało się wczytać schematu – {exc}")

    source_name = file.filename or "dokument.xml"
    data = await file.read()
    return await _convert_xml(data, source_name, validator, output)

@app.post("/convert/file")
async def convert_any(
    request: Request,
    file: UploadFile = File(...),
    schema_file: list[UploadFile] = File(default=[]),
    output: str = Form(default="html"),
    odeslania: bool = Form(default=False),
    walidacja: bool = Form(default=False),
) -> Response:
    """Formularz strony startowej: plik XML albo DOCX (rozpoznany po zawartości),
    wynik do wyboru (HTML, PDF, PDF dostępny albo XML), odesłania na życzenie,
    walidacja względem przesłanego schematu na życzenie (tylko dla HTML)."""
    validator = None
    if walidacja and output == "html":
        try:
            validator = await _resolve_validator(schema_file)
        except SchemaUploadError as exc:
            return _error_response(f"Nie udało się wczytać schematu – {exc}")

    source_name = file.filename or "dokument"
    data = await file.read()
    if not data:
        return _error_response("Przesłany plik jest pusty.")
    xml_name = f"{Path(source_name).stem or 'dokument'}.xml"
    if data[:2] == b"PK":  # a DOCX is a ZIP archive; anything else is taken for XML
        try:
            data = await _docx_to_xml(request, data, source_name)
        except UpstreamError as exc:
            return _error_response(f"Konwersja DOCX → XML nie powiodła się – {exc}")
    if odeslania:
        try:
            data = await _extract_refs(request, data, xml_name)
        except UpstreamError as exc:
            return _error_response(f"Wyszukiwanie odesłań nie powiodło się – {exc}")

    if output == "xml":
        return Response(content=data, media_type="application/xml", headers=_attachment("attachment", xml_name))
    return await _convert_xml(data, xml_name, validator, output)

@app.post("/convert/docx")
async def convert_docx(
    request: Request,
    file: UploadFile = File(...),
    schema_file: list[UploadFile] = File(default=[]),
    output: str = Form(default="html"),
) -> Response:
    try:
        validator = await _resolve_validator(schema_file)
    except SchemaUploadError as exc:
        return _error_response(f"Nie udało się wczytać schematu – {exc}")

    source_name = file.filename or "dokument.docx"
    data = await file.read()
    try:
        xml = await _docx_to_xml(request, data, source_name)
    except UpstreamError as exc:
        return _error_response(f"Konwersja DOCX → XML nie powiodła się – {exc}")

    xml_name = f"{Path(source_name).stem or 'dokument'}.xml"
    try:
        xml = await _extract_refs(request, xml, xml_name)
    except UpstreamError as exc:
        return _error_response(f"Wyszukiwanie odesłań nie powiodło się – {exc}")

    if output == "xml":
        return Response(content=xml, media_type="application/xml", headers=_attachment("attachment", xml_name))
    return await _convert_xml(xml, xml_name, validator, output)
