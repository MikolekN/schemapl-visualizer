"""Convert Polish legal acts in schemaPL XML into HTML and PDF."""

import logging
from importlib.metadata import version

from .conversion import (
    ConversionResult,
    UnsupportedDocument,
    available_formats,
    convert_bytes,
    convert_file,
)
from .pdf.typst import PdfError
from .validation import SchemaValidator, ValidationResult, load_validator

__all__ = [
    "ConversionResult",
    "PdfError",
    "SchemaValidator",
    "UnsupportedDocument",
    "ValidationResult",
    "__version__",
    "available_formats",
    "convert_bytes",
    "convert_file",
    "load_validator",
]

__version__ = version("schemapl-visualizer")

logging.getLogger(__name__).addHandler(logging.NullHandler())
