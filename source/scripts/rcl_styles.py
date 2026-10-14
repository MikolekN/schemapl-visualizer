"""
Generate the Typst table of RCL paragraph styles from a published act's DOCX.

Acts in Dziennik Ustaw and Monitor Polski are typeset in Word with the RCL
template ("szablon aktu prawnego"): every paragraph carries a named style such
as "PKT – punkt" or "Z_LIT/UST(§) – zm. ust. (§) literą". This script resolves
those styles (following basedOn up to the document defaults) and writes their
geometry as a Typst dictionary keyed by the short name ("PKT", "Z_LIT/UST(§)"),
which the official PDF template uses to lay out paragraphs.

    python source/scripts/rcl_styles.py path/to/act.docx [-o source/schemapl_visualizer/pdf/templates/rcl-styles.typ]
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "schemapl_visualizer/pdf/templates/rcl-styles.typ"
WORD_DEFAULT_SIZE = 20  # half-points: Word's 10 pt when nothing sets a size
RCL_STYLE_NAME = re.compile(r"^(?P<short>\S.*?) – ")

ALIGN = {"both": "justify", "center": "center", "right": "right", "end": "right", "left": "left", "start": "left"}


def _on(element: etree._Element | None) -> bool | None:
    """A Word toggle property (<w:b/>, <w:b w:val="0"/>), or None when absent."""
    if element is None:
        return None
    return element.get(W + "val", "true") not in ("0", "false", "off")


def _properties(style: etree._Element) -> dict:
    """The properties a single style element sets itself (no inheritance)."""
    found: dict = {}
    ppr, rpr = style.find(W + "pPr"), style.find(W + "rPr")
    if ppr is not None:
        ind = ppr.find(W + "ind")
        if ind is not None:
            for key, name in (("left", "left"), ("start", "left"), ("right", "right"), ("end", "right")):
                if ind.get(W + key) is not None:
                    found[name] = int(ind.get(W + key))
            if ind.get(W + "hanging") is not None:
                found["first"] = -int(ind.get(W + "hanging"))
            elif ind.get(W + "firstLine") is not None:
                found["first"] = int(ind.get(W + "firstLine"))
        spacing = ppr.find(W + "spacing")
        if spacing is not None:
            for key in ("before", "after", "line"):
                if spacing.get(W + key) is not None:
                    found[key] = int(spacing.get(W + key))
            if spacing.get(W + "lineRule") is not None:
                found["line-rule"] = spacing.get(W + "lineRule")
        jc = ppr.find(W + "jc")
        if jc is not None:
            found["align"] = ALIGN.get(jc.get(W + "val"), "left")
        for tag, name in (("keepNext", "keep-next"), ("keepLines", "keep-lines"),
                          ("pageBreakBefore", "page-break"), ("contextualSpacing", "contextual")):
            value = _on(ppr.find(W + tag))
            if value is not None:
                found[name] = value
    if rpr is not None:
        size = rpr.find(W + "sz")
        if size is not None:
            found["size"] = int(size.get(W + "val"))
        for tag, name in (("b", "bold"), ("i", "italic"), ("caps", "caps"), ("smallCaps", "small-caps")):
            value = _on(rpr.find(W + tag))
            if value is not None:
                found[name] = value
        tracking = rpr.find(W + "spacing")
        if tracking is not None:
            found["tracking"] = int(tracking.get(W + "val"))
        vertical = rpr.find(W + "vertAlign")
        if vertical is not None:
            found["vertical"] = vertical.get(W + "val")
    return found


def resolve_styles(docx: Path) -> dict[str, dict]:
    """Every RCL paragraph style with its effective properties, keyed by short name."""
    with zipfile.ZipFile(docx) as archive:
        styles = etree.fromstring(archive.read("word/styles.xml"))
    by_id = {s.get(W + "styleId"): s for s in styles.iter(W + "style") if s.get(W + "type") == "paragraph"}
    defaults: dict = {"size": WORD_DEFAULT_SIZE}
    doc_defaults = styles.find(W + "docDefaults")
    if doc_defaults is not None:
        for holder in doc_defaults.iter(W + "pPrDefault", W + "rPrDefault"):
            defaults.update(_properties(holder))

    def effective(style_id: str, seen: frozenset = frozenset()) -> dict:
        style = by_id.get(style_id)
        if style is None or style_id in seen:
            return dict(defaults)
        based_on = style.find(W + "basedOn")
        result = effective(based_on.get(W + "val"), seen | {style_id}) if based_on is not None else dict(defaults)
        result.update(_properties(style))  # a style overrides only what it sets, as in Word
        return result

    resolved = {}
    for style_id, style in by_id.items():
        if style.get(W + "customStyle") != "1":
            continue  # Word's built-in styles are not part of the RCL template
        name = style.find(W + "name").get(W + "val")
        match = RCL_STYLE_NAME.match(name)
        resolved[match.group("short") if match else name] = effective(style_id)
    return resolved


def _pt(twips: int) -> str:
    return f"{twips / 20:g}pt"


def to_typst(styles: dict[str, dict], source: str) -> str:
    rows = []
    for short in sorted(styles):
        s = styles[short]
        line_rule = s.get("line-rule", "auto")
        line = s.get("line", 240)
        fields = [
            f"left: {_pt(s.get('left', 0))}",
            f"right: {_pt(s.get('right', 0))}",
            f"first: {_pt(s.get('first', 0))}",
            f"before: {_pt(s.get('before', 0))}",
            f"after: {_pt(s.get('after', 0))}",
            # auto: a multiple of single spacing; atLeast/exact: a distance in points
            f"line: {line / 240:g}" if line_rule == "auto" else f"line: {_pt(line)}",
            f'line-rule: "{line_rule}"',
            f"size: {s.get('size', WORD_DEFAULT_SIZE) / 2:g}pt",
            f'align: "{s.get("align", "left")}"',
            f"tracking: {_pt(s.get('tracking', 0))}",
        ]
        for flag in ("bold", "italic", "caps", "small-caps", "keep-next", "keep-lines", "page-break", "contextual"):
            fields.append(f"{flag}: {'true' if s.get(flag) else 'false'}")
        if s.get("vertical") in ("superscript", "subscript"):
            fields.append(f'vertical: "{s["vertical"]}"')
        key = short.replace("\\", "\\\\").replace('"', '\\"')
        rows.append(f'  "{key}": ({", ".join(fields)}),')
    return (
        "// Generated by source/scripts/rcl_styles.py — do not edit by hand.\n"
        f"// Source: the RCL paragraph styles of {source}.\n"
        "#let rcl-styles = (\n" + "\n".join(rows) + "\n)\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("docx", type=Path, help="a published act in DOCX (Dziennik Ustaw / Monitor Polski)")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    styles = resolve_styles(args.docx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(to_typst(styles, args.docx.name), encoding="utf-8", newline="\n")
    print(f"{len(styles)} styles -> {args.output}")


if __name__ == "__main__":
    main()
