"""
DOCX → XML: the hand-off to the external transformation service.
"""

from __future__ import annotations

import os

from .upstream import Deployment, HttpFileService, credentials, resolve_deployment

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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


def load_docx_service() -> HttpFileService:
    deployment = resolve_deployment(LOCAL, SERVICE)
    username, password = credentials()
    return HttpFileService(
        url=deployment.url,
        field_name=os.environ.get("DOCX_SERVICE_FIELD") or "docxFile",
        media_type=DOCX_MEDIA_TYPE,
        username=username,
        password=password,
        deployment=deployment.name,
    )
