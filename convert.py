"""
Command-line converter for XML.

  python convert.py
  +----------+-------------------+-----------+---------+---------------------------------------------------------------+
  |  OPTION  |       TYPE        | NECESSITY | DEFAULT |                          DESCRIPTION                          |
  +----------+-------------------+-----------+---------+---------------------------------------------------------------+
  |  source  | file or directory | required  |    -    |      XML file or folder containing XML files to convert       |
  |  output  |     directory     | optional  | output  |            Folder to save the converted files into            |
  |  format  |       text        | optional  |  html   |                   Desired conversion format                   |
  |  schema  |       file        | optional  |    -    | XSD file containing the schema definition of the provided XML |
  +----------+-------------------+-----------+---------+---------------------------------------------------------------+

Passing --schema turns on XSD validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.conversion import available_formats, convert_file
from app.validation import load_validator

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "output"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert XML file into a human readable format."
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
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(source.glob("*.xml"))
    return []


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    source = Path(args.source)
    if not source.exists():
        print(f"Path doesn't exist: {source}", file=sys.stderr)
        return 2

    xml_files = collect_xml_files(source)
    if not xml_files:
        print(f"No .xml files in: {source}", file=sys.stderr)
        return 1

    validator = load_validator(args.schema)
    if validator is not None and not validator.compiled:
        print(f"Validation not available: {validator.load_error}", file=sys.stderr)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for xml_file in xml_files:
        try:
            result = convert_file(xml_file, validator=validator, output_format=args.format)
            (output_dir / f"{xml_file.stem}.{result.file_extension}").write_bytes(result.content)
        except Exception as exc:
            failures += 1
            print(f"Conversion error: {xml_file.name}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
