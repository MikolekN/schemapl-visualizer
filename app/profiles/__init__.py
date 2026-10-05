"""
Schema profiles and profile selection.

A *profile* teaches the generic engine how to render one XML vocabulary. The
engine picks a profile by the document's root namespace; unknown documents get
the built-in generic fallback.

PDF profiles typeset a vocabulary straight from its XML; a document no PDF
profile handles cannot be converted to PDF.
"""

from __future__ import annotations

from lxml import etree

from ..engine import GENERIC, Profile
from . import schemapl, schemapl_pdf

_PROFILES = [schemapl.PROFILE]
_PDF_PROFILES = [schemapl_pdf]


def select_profile(root: etree._Element) -> Profile:
    """The profile whose root namespace matches this document, else the generic one."""
    namespace = etree.QName(root).namespace if isinstance(root.tag, str) else None
    for profile in _PROFILES:
        if namespace in getattr(profile, "root_namespaces", ()):
            return profile
    return GENERIC


def select_pdf_profile(root: etree._Element):
    """The PDF profile that can typeset this document, or ``None``."""
    return next((profile for profile in _PDF_PROFILES if profile.handles(root)), None)
