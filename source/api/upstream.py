"""Calls to the other CAISE services."""

from __future__ import annotations

import base64
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Deployment:
    """Where an upstream service is reached, and how to describe it."""

    name: str
    url: str
    note: str


class UpstreamError(RuntimeError):
    """An upstream service could not do its job.

    ``status`` is the HTTP status the service answered with, when it
    answered at all, so a caller can tell "not there (yet)" from "went
    wrong".
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Keep the message and the HTTP status, if there was one."""
        super().__init__(message)
        self.status = status


def resolve_deployment(
    local: Deployment, service: Deployment, *, run_local: bool
) -> Deployment:
    """``local`` when ``run_local`` is set, ``service`` otherwise.

    ``run_local`` is the ``RUN_LOCAL`` setting.
    """
    chosen = local if run_local else service
    log.info(
        "wybrane wdrożenie %r: %s (%s)", chosen.name, chosen.url, chosen.note
    )
    return chosen


@dataclass(frozen=True)
class HttpFileService:
    """POSTs one file to an upstream service, returns the response."""

    url: str
    field_name: str
    media_type: str
    username: str | None = None
    password: str | None = None
    deployment: str = "local"

    def send(
        self, data: bytes, *, filename: str, authorization: str | None = None
    ) -> bytes:
        """Post ``data`` as a file; return the response body."""
        log.info(
            "POST %s - pole %r, plik %r, %d B, %s (wdrożenie %s)",
            self.url,
            self.field_name,
            filename,
            len(data),
            self._sent_scheme(authorization),
            self.deployment,
        )
        return self._open(
            self._build_request(data, filename, authorization), authorization
        )

    def fetch(self, path: str, *, authorization: str | None = None) -> bytes:
        """GET a file the service produced, from the address we call."""
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
        return self._open(
            _request(target, headers=headers), authorization, target
        )

    def _open(
        self,
        request: urllib.request.Request,
        authorization: str | None,
        target: str | None = None,
    ) -> bytes:
        target = target or self.url
        method = request.get_method()
        log.debug(
            "%s %s - nagłówki: %s",
            method,
            target,
            _headers(request.header_items()),
        )
        started = time.monotonic()
        try:
            # requests come from _request, which allows http(s) only
            with urllib.request.urlopen(request) as response:  # noqa: S310
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
                    log.warning(
                        "%s %s - przekierowanie na %s",
                        method,
                        target,
                        final_url,
                    )
        except urllib.error.HTTPError as exc:
            body = exc.read()
            final_url = getattr(exc, "url", None) or target
            # Logged without a traceback: the error goes to the caller.
            log.error(  # noqa: TRY400
                "%s %s -> %s %s po %s%s; treść: %s",
                method,
                target,
                exc.code,
                exc.reason,
                _elapsed(started),
                ""
                if final_url == target
                else f" (po przekierowaniu na {final_url})",
                preview(body) or "(pusta)",
            )
            log.debug(
                "%s %s - nagłówki odpowiedzi: %s",
                method,
                target,
                _headers(exc.headers.items()),
            )
            if exc.code in (401, 403):
                wanted = exc.headers.get("WWW-Authenticate")
                sent = self._sent_scheme(authorization)
                message = (
                    "usługa odrzuciła uwierzytelnienie "
                    f"({exc.code} {exc.reason}) na {method} {target}; "
                    f"wysłano: {sent}"
                    + (f"; usługa oczekuje: {wanted}" if wanted else "")
                )
                raise UpstreamError(message, status=exc.code) from exc
            detail = _first_line(body)
            message = (
                f"usługa odpowiedziała {exc.code} {exc.reason} "
                f"na {method} {target}" + (f" – {detail}" if detail else "")  # noqa: RUF001
            )
            raise UpstreamError(message, status=exc.code) from exc
        except urllib.error.URLError as exc:
            log.error(  # noqa: TRY400
                "%s %s - brak połączenia po %s: %s",
                method,
                target,
                _elapsed(started),
                exc.reason,
            )
            message = f"usługa niedostępna ({target}) – {exc.reason}"  # noqa: RUF001
            raise UpstreamError(message) from exc
        except OSError as exc:
            log.error(  # noqa: TRY400
                "%s %s - błąd połączenia po %s: %s",
                method,
                target,
                _elapsed(started),
                exc,
            )
            message = f"błąd połączenia z usługą ({target}) – {exc}"  # noqa: RUF001
            raise UpstreamError(message) from exc

        if not payload.strip():
            log.error(
                "%s %s -> %s, ale treść jest pusta", method, target, status
            )
            message = f"usługa ({target}) zwróciła pustą odpowiedź"
            raise UpstreamError(message)
        log.debug(
            "%s %s - początek treści: %s", method, target, preview(payload)
        )
        return payload

    def _build_request(
        self, data: bytes, filename: str, authorization: str | None
    ) -> urllib.request.Request:
        """The outgoing call.

        Change this if a service grows extra form fields, a JSON body, a
        query string, or a different auth scheme.
        """
        body, content_type = _multipart(
            self.field_name, filename, data, self.media_type
        )
        headers = {
            "Content-Type": content_type,
            "Accept": "application/xml, text/xml, */*",
        }
        credential = self._authorization(authorization)
        if credential:
            headers["Authorization"] = credential
        return _request(self.url, headers=headers, data=body, method="POST")

    def _authorization(self, incoming: str | None) -> str | None:
        """The credential to send, the most specific one first."""
        if incoming:
            return incoming
        if self.username is not None:
            secret = self.password or ""
            credential = f"{self.username}:{secret}".encode()
            return f"Basic {base64.b64encode(credential).decode('ascii')}"
        return None

    def describe_auth(self) -> str:
        """How calls will authenticate, for status text."""
        return self._sent_scheme(None)

    def _sent_scheme(self, incoming: str | None) -> str:
        """How this call authenticated, for error messages."""
        credential = self._authorization(incoming)
        if credential is None:
            return "bez nagłówka Authorization"
        scheme = credential.split(" ", 1)[0]
        if incoming and credential == incoming:
            return f"{scheme} (nagłówek przekazany od klienta)"
        if scheme == "Basic":
            return f"Basic (użytkownik {self.username})"
        return scheme


def _request(
    url: str,
    *,
    headers: dict[str, str],
    data: bytes | None = None,
    method: str | None = None,
) -> urllib.request.Request:
    """A request for an http(s) address; other schemes are refused."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        message = f"nieobsługiwany adres usługi: {url}"
        raise UpstreamError(message)
    return urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=data, headers=headers, method=method
    )


def _multipart(
    field: str, filename: str, data: bytes, media_type: str
) -> tuple[bytes, str]:
    """A one-file ``multipart/form-data`` body and its Content-Type."""
    boundary = uuid.uuid4().hex
    safe_name = (
        filename.replace('"', "").replace("\r", "").replace("\n", "")
        or "dokument"
    )
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; '
        f'filename="{safe_name}"\r\n'
        f"Content-Type: {media_type}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _first_line(payload: bytes, limit: int = 300) -> str:
    text = payload.decode("utf-8", "replace").strip().splitlines()
    return text[0][:limit] if text else ""


def preview(payload: bytes, limit: int = 500) -> str:
    """A response body squeezed onto one line, for the log."""
    text = " ".join(payload.decode("utf-8", "replace").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _headers(items: Iterable[tuple[str, str]]) -> str:
    """Header names and values, with anything secret held back."""
    return ", ".join(
        f"{name}: {'<ukryte>' if name.lower() == 'authorization' else value}"
        for name, value in items
    )


def _elapsed(started: float) -> str:
    return f"{(time.monotonic() - started) * 1000:.0f} ms"
