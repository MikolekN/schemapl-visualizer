"""Calls to the other CAISE services."""

from __future__ import annotations

import base64
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Deployment:
    name: str
    url: str
    note: str


class UpstreamError(RuntimeError):
    """An upstream service could not do its job.

    ``status`` is the HTTP status the service answered with, when it answered at
    all, so a caller can tell "not there (yet)" from "went wrong".
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def resolve_deployment(local: Deployment, service: Deployment) -> Deployment:
    """``local`` when ``RUN_LOCAL`` is set, ``service`` otherwise."""
    chosen = local if _is_set(os.environ.get("RUN_LOCAL")) else service
    log.info("wybrane wdrożenie %r: %s (%s)", chosen.name, chosen.url, chosen.note)
    return chosen


def _is_set(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def credentials() -> tuple[str | None, str | None]:
    user = os.environ.get("SERVICE_USER")
    password = os.environ.get("SERVICE_PASSWORD")
    return user or None, password or None


@dataclass(frozen=True)
class HttpFileService:
    """POSTs one file to an upstream service and returns its response body."""

    url: str
    field_name: str
    media_type: str
    username: str | None = None
    password: str | None = None
    deployment: str = "local"

    def send(self, data: bytes, *, filename: str, authorization: str | None = None) -> bytes:
        log.info(
            "POST %s - pole %r, plik %r, %d B, %s (wdrożenie %s)",
            self.url,
            self.field_name,
            filename,
            len(data),
            self._sent_scheme(authorization),
            self.deployment,
        )
        return self._open(self._build_request(data, filename, authorization), authorization)

    def fetch(self, path: str, *, authorization: str | None = None) -> bytes:
        """GET a file the service produced, from the address we called it at."""
        headers = {}
        credential = self._authorization(authorization)
        if credential:
            headers["Authorization"] = credential
        target = urllib.parse.urljoin(self.url, path)
        log.info(
            "GET %s - ścieżka %r doklejona do %s, %s",
            target,
            path,
            self.url,
            self._sent_scheme(authorization),
        )
        return self._open(urllib.request.Request(target, headers=headers), authorization, target)

    def _open(
        self, request: urllib.request.Request, authorization: str | None, target: str | None = None
    ) -> bytes:
        target = target or self.url
        method = request.get_method()
        log.debug("%s %s - nagłówki: %s", method, target, _headers(request.header_items()))
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                status, final_url = response.status, response.geturl()
                log.info(
                    "%s %s -> %s %s, %d B, %s, %s",
                    method,
                    target,
                    status,
                    response.reason,
                    len(payload),
                    response.headers.get("Content-Type") or "bez Content-Type",
                    _elapsed(started),
                )
                log.debug(
                    "%s %s - nagłówki odpowiedzi: %s",
                    method,
                    target,
                    _headers(response.headers.items()),
                )
                if final_url != target:
                    log.warning("%s %s - przekierowanie na %s", method, target, final_url)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            final_url = getattr(exc, "url", None) or target
            log.error(
                "%s %s -> %s %s po %s%s; treść: %s",
                method,
                target,
                exc.code,
                exc.reason,
                _elapsed(started),
                "" if final_url == target else f" (po przekierowaniu na {final_url})",
                preview(body) or "(pusta)",
            )
            log.debug(
                "%s %s - nagłówki odpowiedzi: %s", method, target, _headers(exc.headers.items())
            )
            if exc.code in (401, 403):
                wanted = exc.headers.get("WWW-Authenticate")
                raise UpstreamError(
                    f"usługa odrzuciła uwierzytelnienie ({exc.code} {exc.reason}) "
                    f"na {method} {target}; wysłano: {self._sent_scheme(authorization)}"
                    + (f"; usługa oczekuje: {wanted}" if wanted else ""),
                    status=exc.code,
                ) from exc
            detail = _first_line(body)
            raise UpstreamError(
                f"usługa odpowiedziała {exc.code} {exc.reason} na {method} {target}"
                + (f" – {detail}" if detail else ""),
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            log.error(
                "%s %s - brak połączenia po %s: %s", method, target, _elapsed(started), exc.reason
            )
            raise UpstreamError(f"usługa niedostępna ({target}) – {exc.reason}") from exc
        except OSError as exc:
            log.error(
                "%s %s - błąd połączenia po %s: %s", method, target, _elapsed(started), exc
            )
            raise UpstreamError(f"błąd połączenia z usługą ({target}) – {exc}") from exc

        if not payload.strip():
            log.error("%s %s -> %s, ale treść jest pusta", method, target, status)
            raise UpstreamError(f"usługa ({target}) zwróciła pustą odpowiedź")
        log.debug("%s %s - początek treści: %s", method, target, preview(payload))
        return payload

    def _build_request(
        self, data: bytes, filename: str, authorization: str | None
    ) -> urllib.request.Request:
        """The outgoing call. Change this if a service grows extra form fields,
        a JSON body, a query string, or a different auth scheme."""
        body, content_type = _multipart(self.field_name, filename, data, self.media_type)
        headers = {"Content-Type": content_type, "Accept": "application/xml, text/xml, */*"}
        credential = self._authorization(authorization)
        if credential:
            headers["Authorization"] = credential
        return urllib.request.Request(self.url, data=body, headers=headers, method="POST")

    def _authorization(self, incoming: str | None) -> str | None:
        """Whatever this deployment authenticates with, most specific first."""
        if incoming:
            return incoming
        if self.username is not None:
            secret = self.password or ""
            credential = f"{self.username}:{secret}".encode("utf-8")
            return f"Basic {base64.b64encode(credential).decode('ascii')}"
        return None

    def describe_auth(self) -> str:
        """How calls will authenticate, for status text."""
        return self._sent_scheme(None)

    def _sent_scheme(self, incoming: str | None) -> str:
        """How this call authenticated — for error messages worth reading."""
        credential = self._authorization(incoming)
        if credential is None:
            return "bez nagłówka Authorization"
        scheme = credential.split(" ", 1)[0]
        if incoming and credential == incoming:
            return f"{scheme} (nagłówek przekazany od klienta)"
        if scheme == "Basic":
            return f"Basic (użytkownik {self.username})"
        return scheme


def _multipart(field: str, filename: str, data: bytes, media_type: str) -> tuple[bytes, str]:
    """A one-file ``multipart/form-data`` body and its Content-Type header."""
    boundary = uuid.uuid4().hex
    safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "") or "dokument"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{safe_name}"\r\n'
        f"Content-Type: {media_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _first_line(payload: bytes, limit: int = 300) -> str:
    text = payload.decode("utf-8", "replace").strip().splitlines()
    return text[0][:limit] if text else ""


def preview(payload: bytes, limit: int = 500) -> str:
    """A response body squeezed onto one line, for the log."""
    text = " ".join(payload.decode("utf-8", "replace").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _headers(items) -> str:
    """Header names and values, with anything secret held back."""
    return ", ".join(
        f"{name}: {'<ukryte>' if name.lower() == 'authorization' else value}"
        for name, value in items
    )


def _elapsed(started: float) -> str:
    return f"{(time.monotonic() - started) * 1000:.0f} ms"
