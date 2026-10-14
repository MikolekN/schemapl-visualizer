"""The Jinja-rendered HTML page of a converted document."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import jinja2
from markupsafe import Markup

from ..validation import ValidationResult

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_full_page(
    *,
    body_html: Markup,
    toc_html: Markup,
    metadata_html: Markup,
    validation: ValidationResult,
    uses_math: bool,
    source_name: str,
) -> str:
    template = _environment.get_template("page.html.j2")
    return template.render(
        title=source_name,
        source_name=source_name,
        validated=validation.validated,
        valid=validation.is_valid,
        errors=validation.errors,
        schema_error=validation.schema_error,
        needs_mathjax=uses_math,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        body=body_html,
        toc=toc_html,
        metadata=metadata_html,
    )
