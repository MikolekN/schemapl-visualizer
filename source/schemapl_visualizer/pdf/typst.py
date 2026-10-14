"""
Typst: the typesetting engine behind PDF output.

A PDF is typeset straight from the XML. A PDF profile walks the document and
writes Typst code that calls the functions of a layout template
(``pdf/templates/*.typ``); Typst compiles that code into the PDF. This
module holds the helpers for writing the code safely and the compile step.

Text from the document never becomes Typst markup: it is always emitted as a
string literal, so nothing in a document can change the layout code.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Collapsible whitespace - not the no-break space, which typesetting must keep.
_WHITESPACE = re.compile(r"[ \t\n\r\f\v]+")
# No space after an opening quotation mark, none before a closing one or punctuation
# (the whitespace between elements of a pretty-printed file would put one there).
_OPENING_QUOTE = "\u201e"
_NO_SPACE_BEFORE = ("\u201d", ",", ".", ";", ":", ")", "!", "?")


def string(value: str) -> str:
    """A Typst string literal."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def literal(value: object) -> str:
    """A Python value as a Typst expression (str, bool, None, numbers, lists, dicts, code)."""
    if isinstance(value, Code):
        return value.source
    if isinstance(value, Inline):
        return "[" + value.markup() + "]"
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return string(value)
    if isinstance(value, dict):
        if not value:
            return "(:)"
        return "(" + ", ".join(f"{key}: {literal(item)}" for key, item in value.items()) + ")"
    if isinstance(value, (list, tuple)):
        items = [literal(item) for item in value]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    raise TypeError(f"no Typst literal for {type(value).__name__}")


@dataclass(frozen=True)
class Code:
    """Raw Typst code: an expression (e.g. ``1.5em``) or a content block (``[...]``)."""

    source: str


def call(function: str, *args: object, body: "Inline | Code | None" = None, **kwargs: object) -> Code:
    """``function(args, key: value)[body]`` as an expression (no leading ``#``)."""
    parts = [literal(arg) for arg in args]
    parts += [f"{key.replace('_', '-')}: {literal(item)}" for key, item in kwargs.items() if item is not None]
    code = f"{function}({', '.join(parts)})"
    if body is not None:
        code += content(body).source
    return Code(code)


def content(body: "Inline | Code") -> Code:
    """A content block ``[...]``."""
    if isinstance(body, Inline):
        return Code("[" + body.markup() + "]")
    return body if body.source.startswith("[") else Code(f"[#{body.source}]")


@dataclass
class _Wrapped:
    function: str
    args: tuple
    inner: "Inline"


@dataclass
class Inline:
    """Running text of one paragraph: text, wrapped runs (bold, links, ...) and atoms.

    Whitespace is collapsed across the whole run - as in a typeset paragraph -
    and trimmed at its ends, so the indentation of a pretty-printed XML file
    never reaches the PDF.
    """

    items: list = field(default_factory=list)

    def text(self, value: str | None) -> "Inline":
        if value:
            self.items.append(value)
        return self

    def wrap(self, function: str, inner: "Inline", *args: object) -> "Inline":
        if inner.items:
            self.items.append(_Wrapped(function, args, inner))
        return self

    def atom(self, code: Code) -> "Inline":
        """Content that is not text: a footnote call, a formula, a line break."""
        self.items.append(code)
        return self

    def extend(self, other: "Inline") -> "Inline":
        self.items.extend(other.items)
        return self

    def is_empty(self) -> bool:
        return not self.items

    def plain(self) -> str:
        """The visible text only (for alt texts and metadata)."""
        parts = []
        for item in self.items:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, _Wrapped):
                parts.append(item.inner.plain())
        return _WHITESPACE.sub(" ", "".join(parts)).strip()

    def markup(self) -> str:
        return "".join(self._emit(self._collapse()))

    # -- whitespace ------------------------------------------------------------------

    def _collapse(self) -> dict[tuple[int, int], str]:
        """Collapsed text of every text item, keyed by (run, position), trimmed at both ends."""
        flat: list[tuple[tuple[int, int], str | None]] = []

        def walk(inline: Inline) -> None:
            for position, item in enumerate(inline.items):
                if isinstance(item, str):
                    flat.append(((id(inline), position), item))
                elif isinstance(item, _Wrapped):
                    walk(item.inner)
                else:
                    flat.append(((id(inline), position), None))  # an atom: not whitespace

        walk(self)
        result: dict[tuple[int, int], str] = {}
        after_space = True  # at the start, leading whitespace goes
        last = None  # the text written last, whose space a closing quote takes back
        for key, value in flat:
            if value is None:
                after_space, last = False, None
                continue
            core = _WHITESPACE.sub(" ", value).strip(" ")
            if not core:
                collapsed = "" if after_space else " "
            else:
                lead = " " if _WHITESPACE.match(value[:1]) and not after_space else ""
                if core.startswith(_NO_SPACE_BEFORE):
                    lead = ""
                    if last is not None:
                        result[last] = result[last].rstrip(" ")
                trail = " " if _WHITESPACE.match(value[-1:]) else ""
                collapsed = lead + core + trail
            result[key] = collapsed
            if collapsed:  # a no-break space takes the place of the space after it
                after_space = collapsed.endswith((" ", "\u00a0", _OPENING_QUOTE))
                last = key
        for key, value in reversed(flat):  # trailing whitespace goes
            if value is None:
                break
            result[key] = result[key].rstrip(" ")
            if result[key]:
                break
        return result

    def _emit(self, texts: dict[tuple[int, int], str]) -> Iterable[str]:
        for position, item in enumerate(self.items):
            if isinstance(item, str):
                value = texts.get((id(self), position), "")
                if value:
                    yield "#" + string(value)
            elif isinstance(item, _Wrapped):
                inner = "".join(item.inner._emit(texts))
                if inner:
                    args = ", ".join(literal(arg) for arg in item.args)
                    yield f"#{item.function}({args})[{inner}]"
            else:
                yield "#" + item.source


class PdfError(RuntimeError):
    """Typst could not typeset the document."""


def compile_pdf(source: str, *, standards: Sequence[str] = (), inputs: Mapping[str, str] | None = None) -> bytes:
    """Typeset Typst ``source`` (which imports a template from TEMPLATE_DIR) into a PDF.

    ``inputs`` reach the template as ``sys.inputs`` (e.g. which version of a layout to set).
    """
    import typst  # imported lazily: only PDF output needs it

    try:
        return typst.compile(
            source.encode("utf-8"),
            root=str(TEMPLATE_DIR),
            format="pdf",
            pdf_standards=list(standards),
            sys_inputs=dict(inputs or {}),
        )
    except typst.TypstError as exc:
        raise PdfError(str(exc)) from exc
