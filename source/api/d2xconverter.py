"""DOCX → XML: the hand-off to the external transformation service."""

from __future__ import annotations

from settings import Settings
from upstream import Deployment, HttpFileService, resolve_deployment

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


LOCAL = Deployment(
    "local",
    "https://d2xconverter.lex.nlp.caise.pl/parse_xml",
    "przez internet, wymaga poświadczeń",
)

SERVICE = Deployment(
    "service",
    "http://s04c-d2xconverter:8080/parse_xml",
    "po nazwie usługi, bez uwierzytelnienia",
)


def load_docx_service(settings: Settings) -> HttpFileService:
    """The DOCX → XML converter this process should call."""
    deployment = resolve_deployment(
        LOCAL, SERVICE, run_local=settings.run_local
    )
    return HttpFileService(
        url=deployment.url,
        field_name=settings.docx_service_field,
        media_type=DOCX_MEDIA_TYPE,
        username=settings.service_user,
        password=settings.password,
        deployment=deployment.name,
    )
