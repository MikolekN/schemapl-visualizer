"""
Validator object

Provides an object responsible for loading XML Schema, validating
provided XML file, and sharing validation status and errors.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from lxml import etree


class ValidationStatus(Enum):
    SKIPPED = "skipped"
    VALID = "valid"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ValidationResult:

    status: ValidationStatus
    errors: tuple[str, ...] = ()
    schema_error: str | None = None

    @property
    def validated(self) -> bool:
        return self.status in (ValidationStatus.VALID, ValidationStatus.INVALID)

    @property
    def is_valid(self) -> bool:
        return self.status is ValidationStatus.VALID

    @classmethod
    def skipped(cls) -> ValidationResult:
        return cls(ValidationStatus.SKIPPED)

    @classmethod
    def valid(cls) -> ValidationResult:
        return cls(ValidationStatus.VALID)

    @classmethod
    def invalid(cls, errors: list[str]) -> ValidationResult:
        return cls(ValidationStatus.INVALID, tuple(errors))

    @classmethod
    def unavailable(cls, schema_error: str | None) -> ValidationResult:
        return cls(ValidationStatus.UNAVAILABLE, (), schema_error)


class SchemaValidator:

    def __init__(self, schema_path: Path | str) -> None:
        self.path = Path(schema_path)
        self.compiled = False
        self.load_error: str | None = None
        self._schema: etree.XMLSchema | None = None
        try:
            document = etree.parse(str(self.path))
            self._schema = etree.XMLSchema(document)
            self.compiled = True
        except Exception as exc:
            self.load_error = f"{type(exc).__name__}: {exc}"

    def validate(self, root: etree._Element) -> ValidationResult:
        if not self.compiled or self._schema is None:
            return ValidationResult.unavailable(self.load_error)
        if self._schema.validate(root):
            return ValidationResult.valid()
        errors = [
            f"wiersz {entry.line}, kol. {entry.column}: {entry.message}"
            for entry in self._schema.error_log
        ]
        return ValidationResult.invalid(errors)


def load_validator(schema_path: Path | str | None) -> SchemaValidator | None:
    return SchemaValidator(schema_path) if schema_path else None


class SchemaUploadError(ValueError):
    """The uploaded files do not amount to a usable schema."""


def load_validator_from_uploads(files: Sequence[tuple[str, bytes]]) -> SchemaValidator:
    """Compile a schema that arrived with the request instead of living on disk."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, data in files:
            if name.lower().endswith(".zip"):
                _extract_schema_zip(data, root)
            elif data and Path(name).name:
                (root / Path(name).name).write_bytes(data)

        candidates = _entry_points(root)
        if not candidates:
            raise SchemaUploadError("wśród przesłanych plików nie ma pliku .xsd")
        validators = []
        for candidate in candidates:
            validator = SchemaValidator(candidate)
            if validator.compiled:
                return validator
            validators.append(validator)
        return validators[0]  # none compiles: report the main schema's error


def _extract_schema_zip(data: bytes, root: Path) -> None:
    """Unpack the ``.xsd`` files of a zipped schema, keeping their layout."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SchemaUploadError(f"nie udało się odczytać archiwum .zip – {exc}") from exc
    with archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.lower().endswith(".xsd"):
                continue
            target = (root / entry.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                continue  # zip-slip: an entry pointing outside the directory
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))


def _entry_points(root: Path) -> list[Path]:
    """Uploaded schemas nothing else references; all of them if every one is referenced.

    A referenced schema is only a part of another one. Validating against it
    when the main schema fails to compile would report every document invalid.
    """
    schemas = sorted(root.rglob("*.xsd"))
    referenced: set[Path] = set()
    for path in schemas:
        try:
            document = etree.parse(str(path))
        except etree.XMLSyntaxError:
            continue
        for element in document.iter(
            "{http://www.w3.org/2001/XMLSchema}import",
            "{http://www.w3.org/2001/XMLSchema}include",
            "{http://www.w3.org/2001/XMLSchema}redefine",
        ):
            location = element.get("schemaLocation")
            if location and "://" not in location:
                referenced.add((path.parent / location).resolve())
    return [path for path in schemas if path.resolve() not in referenced] or schemas
