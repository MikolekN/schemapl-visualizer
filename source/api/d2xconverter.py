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

# The experimental version of the converter, called instead of the
# usual one when the request asks for it. Its endpoint takes the file
# in another form field (DOCX_EXPERIMENTAL_SERVICE_FIELD).
EXPERIMENTAL_LOCAL = Deployment(
    "local",
    "https://d2xconverter-experimental.lex.nlp.caise.pl/v1/convert",
    "przez internet, wymaga poświadczeń",
)

EXPERIMENTAL_SERVICE = Deployment(
    "service",
    "http://s04c-d2xconverter-experimental:8080/v1/convert",
    "po nazwie usługi, bez uwierzytelnienia",
)


def load_docx_service(
    settings: Settings, *, experimental: bool = False
) -> HttpFileService:
    """The DOCX → XML converter this process should call.

    ``experimental``: its experimental version instead.
    """
    local, service = (
        (EXPERIMENTAL_LOCAL, EXPERIMENTAL_SERVICE)
        if experimental
        else (LOCAL, SERVICE)
    )
    deployment = resolve_deployment(
        local, service, run_local=settings.run_local
    )
    return HttpFileService(
        url=deployment.url,
        field_name=(
            settings.docx_experimental_service_field
            if experimental
            else settings.docx_service_field
        ),
        media_type=DOCX_MEDIA_TYPE,
        username=settings.service_user,
        password=settings.password,
        deployment=deployment.name,
    )
