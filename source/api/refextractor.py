"""XML → XML: the hand-off to the reference extractor."""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
from dataclasses import dataclass

from settings import Settings
from upstream import (
    Deployment,
    HttpFileService,
    UpstreamError,
    preview,
    resolve_deployment,
)

log = logging.getLogger(__name__)

XML_MEDIA_TYPE = "application/xml"

# The extractor writes the result some time after it answers the POST,
# so the address it names is a 404 until then. How long we are willing
# to wait for it:
RESULT_RETRIES = 10
RESULT_DELAY_SECONDS = 5.0


LOCAL = Deployment(
    "local",
    "https://refextractor.lex.nlp.caise.pl/xml-to-xml",
    "przez internet, wymaga poświadczeń",
)

SERVICE = Deployment(
    "service",
    "http://s13a-refextractor:8000/xml-to-xml",
    "po nazwie usługi, bez uwierzytelnienia",
)


@dataclass(frozen=True)
class RefExtractor:
    """Posts the document, then fetches the XML it was turned into."""

    upstream: HttpFileService
    retries: int = RESULT_RETRIES
    delay: float = RESULT_DELAY_SECONDS

    @property
    def url(self) -> str:
        """The address documents are posted to."""
        return self.upstream.url

    @property
    def deployment(self) -> str:
        """The name of the deployment in use."""
        return self.upstream.deployment

    def describe_auth(self) -> str:
        """How calls will authenticate, for status text."""
        return self.upstream.describe_auth()

    def send(
        self, data: bytes, *, filename: str, authorization: str | None = None
    ) -> bytes:
        """Send the document; return it with its references marked."""
        log.info(
            "wyszukiwanie odesłań: %s, plik %r, %d B, %s",
            self.url,
            filename,
            len(data),
            self.describe_auth(),
        )
        envelope = self.upstream.send(
            data, filename=filename, authorization=authorization
        )
        return self._await_result(
            _result_path(envelope, self.url), authorization
        )

    def _await_result(self, path: str, authorization: str | None) -> bytes:
        """The result, once the extractor has written it.

        It answers 404 while the work is still running, so that one
        status is worth waiting on; every other failure is real and goes
        straight up.
        """
        for attempt in range(1, self.retries + 1):
            try:
                return self.upstream.fetch(path, authorization=authorization)
            except UpstreamError as exc:
                if exc.status != 404:
                    raise
                log.info(
                    "wyniku jeszcze nie ma (404, próba %d z %d) – "  # noqa: RUF001
                    "ponawiamy za %.0f s",
                    attempt,
                    self.retries + 1,
                    self.delay,
                )
                time.sleep(self.delay)
        log.warning(
            "po %d próbach i %.0f s czekania wyniku wciąż nie ma – "  # noqa: RUF001
            "ostatnia próba",
            self.retries,
            self.retries * self.delay,
        )
        return self.upstream.fetch(path, authorization=authorization)


def _result_path(payload: bytes, base_url: str) -> str:
    """The path of ``xml_file_url`` in the extractor's reply."""
    log.info(
        "odpowiedź ekstraktora (%d B): %s", len(payload), preview(payload)
    )
    try:
        envelope = json.loads(payload)
    except ValueError as exc:
        # The caller logs the traceback of the error raised here.
        log.error(  # noqa: TRY400
            "odpowiedź ekstraktora nie jest JSON-em: %s", preview(payload)
        )
        message = (
            f"nieoczekiwana odpowiedź usługi (nie JSON): {payload[:120]!r}"
        )
        raise UpstreamError(message) from exc
    url = envelope.get("xml_file_url") if isinstance(envelope, dict) else None
    if not url:
        keys = (
            ", ".join(sorted(envelope)) if isinstance(envelope, dict) else "-"
        )
        log.error(
            "w odpowiedzi ekstraktora brakuje xml_file_url; pola: %s", keys
        )
        message = f"odpowiedź usługi bez pola xml_file_url (pola: {keys})"
        raise UpstreamError(message)
    parts = urllib.parse.urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    log.info(
        "ekstraktor wskazał xml_file_url=%s, pobieramy ścieżkę %s", url, path
    )
    _warn_on_foreign_host(parts, base_url)
    return path


def _warn_on_foreign_host(
    parts: urllib.parse.SplitResult, base_url: str
) -> None:
    """Warn when the reply names a host other than the one we call.

    That is the usual cause of a 404 when fetching the result.
    """
    base = urllib.parse.urlsplit(base_url)
    if parts.netloc and parts.netloc != base.netloc:
        log.warning(
            "xml_file_url wskazuje na %s, a odpytujemy %s – "  # noqa: RUF001
            "pobieramy z %s, "
            "więc jeśli ścieżka tam nie istnieje, dostaniemy 404",
            parts.netloc,
            base.netloc,
            base.netloc,
        )


def load_ref_service(settings: Settings) -> RefExtractor:
    """The reference extractor this process should call."""
    deployment = resolve_deployment(
        LOCAL, SERVICE, run_local=settings.run_local
    )
    return RefExtractor(
        HttpFileService(
            url=deployment.url,
            field_name=settings.ref_service_field,
            media_type=XML_MEDIA_TYPE,
            username=settings.service_user,
            password=settings.password,
            deployment=deployment.name,
        )
    )
