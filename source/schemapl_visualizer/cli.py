"""Command-line converter for XML.

    schemapl-visualizer SOURCE [-o OUTPUT] [-f FORMAT] [--schema XSD]

Also run as ``python -m schemapl_visualizer``. SOURCE is an XML file or
a folder of XML files. Each result is saved in OUTPUT (default:
``output`` in the current directory) in FORMAT: html (the default), pdf
or pdf-accessible. Passing --schema turns on XSD validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .conversion import available_formats, convert_file
from .validation import load_validator

# Relative to the directory the command is run from.
DEFAULT_OUTPUT = Path("output")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """The command-line options; ``None`` reads ``sys.argv``."""
    parser = argparse.ArgumentParser(
        prog="schemapl-visualizer",
        description="Convert XML file into a human readable format.",
    )
    parser.add_argument(
        "source",
        help="XML file or folder containing XML files to convert",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="output folder",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=available_formats(),
        default="html",
        help="output format",
    )
    parser.add_argument(
        "--schema",
        help="path to an XSD; passing it turns XSD validation on",
    )
    return parser.parse_args(argv)


def collect_xml_files(source: Path) -> list[Path]:
    """The file itself, or the XML files of a folder, sorted."""
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(source.glob("*.xml"))
    return []


def main(argv: list[str] | None = None) -> int:
    """Convert the files: 0 on success, 1 on failure, 2 no input."""
    args = parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        sys.stderr.write(f"Path doesn't exist: {source}\n")
        return 2

    xml_files = collect_xml_files(source)
    if not xml_files:
        sys.stderr.write(f"No .xml files in: {source}\n")
        return 1

    validator = load_validator(args.schema)
    if validator is not None and not validator.compiled:
        sys.stderr.write(f"Validation not available: {validator.load_error}\n")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for xml_file in xml_files:
        try:
            result = convert_file(
                xml_file, validator=validator, output_format=args.format
            )
            (
                output_dir / f"{xml_file.stem}.{result.file_extension}"
            ).write_bytes(result.content)
        except Exception as exc:
            failures += 1
            sys.stderr.write(f"Conversion error: {xml_file.name}: {exc}\n")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
