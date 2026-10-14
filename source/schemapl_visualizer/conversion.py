"""
Convert XML into an output document format.

Every format is produced from the XML itself: HTML by the rendering engine,
PDF by a PDF profile and Typst.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path

from lxml import etree

from .html.page import render_full_page
from .parsing import parse_xml
from .html.engine import RenderState, render_document_body, render_toc
from .profiles import select_pdf_profile, select_profile
from .pdf.typst import compile_pdf
from .validation import SchemaValidator, ValidationResult


@dataclass(frozen=True)
class ConversionResult:
    content: bytes
    media_type: str
    file_extension: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


class UnsupportedDocument(ValueError):
    """The document cannot be converted to the requested format."""


def convert_bytes(
    data: bytes,
    *,
    source_name: str,
    validator: SchemaValidator | None = None,
    output_format: str = "html",
) -> ConversionResult:
    root = parse_xml(data)
    validation = validator.validate(root) if validator is not None else ValidationResult.skipped()
    build_output = OUTPUT_FORMATS.get(output_format)
    if build_output is None:
        raise ValueError(
            f"Unknown output format: {output_format!r}. Available: {', '.join(available_formats())}."
        )
    return build_output(root, source_name, validation)


def convert_file(
    path: Path | str,
    *,
    validator: SchemaValidator | None = None,
    output_format: str = "html",
) -> ConversionResult:
    path = Path(path)
    return convert_bytes(
        path.read_bytes(),
        source_name=path.name,
        validator=validator,
        output_format=output_format,
    )


def _to_html(
    root: etree._Element, source_name: str, validation: ValidationResult
) -> ConversionResult:
    state = RenderState(profile=select_profile(root))
    body_html = render_document_body(root, state)
    page = render_full_page(
        body_html=body_html,
        toc_html=render_toc(state.toc),
        metadata_html=state.metadata_html,
        validation=validation,
        uses_math=state.uses_math,
        source_name=source_name,
    )
    return ConversionResult(page.encode("utf-8"), "text/html; charset=utf-8", "html")


def _to_pdf(
    root: etree._Element,
    source_name: str,
    validation: ValidationResult,
    *,
    variant: str,
    extension: str,
) -> ConversionResult:
    profile = select_pdf_profile(root)
    if profile is None:
        raise UnsupportedDocument("PDF output is available for schemaPL documents only.")
    source, standards, inputs = profile.typst_source(root, variant)
    return ConversionResult(compile_pdf(source, standards=standards, inputs=inputs), "application/pdf", extension)


OUTPUT_FORMATS = {
    "html": _to_html,
    # as published in the official journal
    "pdf": partial(_to_pdf, variant="official", extension="pdf"),
    # the same in large print for visually impaired readers, tagged PDF/UA-1
    "pdf-accessible": partial(_to_pdf, variant="accessible", extension="accessible.pdf"),
}


def available_formats() -> list[str]:
    return sorted(OUTPUT_FORMATS)
