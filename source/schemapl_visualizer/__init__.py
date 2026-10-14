"""Convert Polish legal acts in schemaPL XML into HTML and PDF."""

import logging
from importlib.metadata import version

from .conversion import (
    ConversionResult,
    UnsupportedDocumentError,
    available_formats,
    convert_bytes,
    convert_file,
)
from .parsing import MAX_DEPTH, DocumentTooDeepError
from .pdf.typst import PdfError
from .validation import SchemaValidator, ValidationResult, load_validator

__all__ = [
    "MAX_DEPTH",
    "ConversionResult",
    "DocumentTooDeepError",
    "PdfError",
    "SchemaValidator",
    "UnsupportedDocumentError",
    "ValidationResult",
    "__version__",
    "available_formats",
    "convert_bytes",
    "convert_file",
    "load_validator",
]

__version__ = version("schemapl-visualizer")

logging.getLogger(__name__).addHandler(logging.NullHandler())
