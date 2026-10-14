"""Test the command-line converter."""

from pathlib import Path

import pytest

from schemapl_visualizer.cli import DEFAULT_OUTPUT, main, parse_args


def test_converts_a_file(tmp_path: Path, math_act: bytes) -> None:
    """Writes the result to the output folder under the act's name."""
    source = tmp_path / "akt.xml"
    source.write_bytes(math_act)
    output = tmp_path / "out"

    status = main([str(source), "-o", str(output), "-f", "pdf"])

    assert status == 0
    assert (output / "akt.pdf").read_bytes().startswith(b"%PDF-")


def test_converts_a_folder(
    tmp_path: Path, math_act: bytes, generic_xml: bytes
) -> None:
    """Converts every XML file in a folder."""
    (tmp_path / "a.xml").write_bytes(math_act)
    (tmp_path / "b.xml").write_bytes(generic_xml)
    (tmp_path / "notes.txt").write_text("not XML", encoding="utf-8")
    output = tmp_path / "out"

    status = main([str(tmp_path), "-o", str(output)])

    assert status == 0
    assert sorted(path.name for path in output.iterdir()) == [
        "a.html",
        "b.html",
    ]


def test_missing_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails with status 2 when the source does not exist."""
    status = main([str(tmp_path / "missing.xml")])

    assert status == 2
    assert "doesn't exist" in capsys.readouterr().err


def test_folder_without_xml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails with status 1 when a folder has no XML files."""
    status = main([str(tmp_path)])

    assert status == 1
    assert "No .xml files" in capsys.readouterr().err


def test_failed_conversion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reports a file it cannot convert and fails with status 1."""
    source = tmp_path / "broken.xml"
    source.write_bytes(b"<doc>")

    status = main([str(source), "-o", str(tmp_path / "out")])

    assert status == 1
    assert "Conversion error: broken.xml" in capsys.readouterr().err


def test_unusable_schema(
    tmp_path: Path, generic_xml: bytes, capsys: pytest.CaptureFixture[str]
) -> None:
    """Warns about a schema it cannot load and converts anyway."""
    source = tmp_path / "doc.xml"
    source.write_bytes(generic_xml)

    status = main(
        [
            str(source),
            "-o",
            str(tmp_path / "out"),
            "--schema",
            str(tmp_path / "x.xsd"),
        ]
    )

    assert status == 0
    assert "Validation not available" in capsys.readouterr().err


def test_default_output_is_relative_to_working_directory() -> None:
    """Writes to ./output unless told otherwise."""
    args = parse_args(["akt.xml"])

    assert Path(args.output) == DEFAULT_OUTPUT
    assert not DEFAULT_OUTPUT.is_absolute()
