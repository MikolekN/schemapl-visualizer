"""MathML for PDF output: Typst math, and the formula read aloud.

Presentation MathML becomes Typst math, or a sentence in Polish.

``typst_math`` gives the body of a Typst equation (what goes between
``$``), set by Typst's own math layout. ``spoken`` gives the formula as
a sentence: the alternative text an accessible PDF needs for it.

Document text never becomes Typst syntax: a token is emitted as a lone
letter or digit run, an operator character, an escaped ASCII character
or a string literal - nothing in a formula can change the layout code.
"""

from __future__ import annotations

import re
import unicodedata

from lxml import etree

from .typst import string

MATHML = "http://www.w3.org/1998/Math/MathML"

# ASCII operators Typst math reads as themselves; other ASCII
# punctuation is escaped.
_BARE = {"+": "+", "-": "−", "=": "=", "<": "<", ">": ">", "!": "!"}  # noqa: RUF001
# Opening and closing delimiters that may stretch around what they
# enclose.
_FENCES = {
    "(": ")",
    "[": "]",
    "{": "}",
    "|": "|",
    "‖": "‖",
    "⟨": "⟩",
    "⌈": "⌉",
    "⌊": "⌋",
}
_INVISIBLE = {"⁡", "⁢", "⁣", "⁤"}
# Accents placed over a base (mover with accent="true", or these
# characters).
_ACCENTS = {
    "^",
    "ˆ",  # noqa: RUF001
    "̂",
    "~",
    "˜",  # noqa: RUF001
    "̃",
    "˙",
    "̇",
    "¨",
    "̈",
    "→",
    "⃗",
    "ˇ",
    "̌",
    "´",  # noqa: RUF001
    "́",
    "`",
    "̀",
}
_OVERLINES = {"‾", "¯", "̅", "_"}

_SPACES = ((1.0, "quad"), (0.27, "thick"), (0.22, "med"), (0.0, "thin"))


def _local(element: etree._Element) -> str:
    return (
        etree.QName(element).localname if isinstance(element.tag, str) else ""
    )


def _children(element: etree._Element) -> list[etree._Element]:
    return [
        child
        for child in element
        if isinstance(child.tag, str)
        and etree.QName(child).namespace == MATHML
    ]


def _text(element: etree._Element) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


# -- Typst -------------------------------------------------------------


def typst_math(math: etree._Element) -> str:
    """The equation body (Typst math) of a <math> element."""
    return _row(_children(math)) or '""'


def _row(children: list[etree._Element]) -> str:
    """A sequence; fences around it become a stretching lr(...)."""
    parts = [_node(child) for child in children]
    if (
        len(children) >= 2
        and _local(children[0]) == "mo"
        and _local(children[-1]) == "mo"
        and _text(children[0]) in _FENCES
        and _FENCES[_text(children[0])] == _text(children[-1])
    ):
        inner = " ".join(part for part in parts[1:-1] if part)
        opening, closing = (
            _char(_text(children[0])),
            _char(_text(children[-1])),
        )
        return f"lr({opening} {inner} {closing})"
    return " ".join(part for part in parts if part)


def _arg(element: etree._Element | None) -> str:
    """A function argument: never empty."""
    return (_node(element) if element is not None else "") or '""'


def _node(element: etree._Element) -> str:
    name = _local(element)
    kids = _children(element)
    if name in ("math", "mrow", "mstyle", "mpadded", "merror", "menclose"):
        return _row(kids)
    if name == "mfenced":
        opening, closing = element.get("open", "("), element.get("close", ")")
        separators = (element.get("separators", ",") or "").replace(" ", "")
        items = []
        for index, kid in enumerate(kids):
            if index and separators:
                items.append(
                    _char(separators[min(index - 1, len(separators) - 1)])
                )
            items.append(_node(kid))
        inner = " ".join(item for item in items if item)
        open_code = _char(opening) if opening else ""
        close_code = _char(closing) if closing else ""
        return (
            f"lr({open_code} {inner} {close_code})"
            if open_code and close_code
            else f"{open_code} {inner} {close_code}"
        )
    if name == "semantics":
        return _node(kids[0]) if kids else ""
    if name in (
        "annotation",
        "annotation-xml",
        "none",
        "mprescripts",
        "maligngroup",
        "malignmark",
    ):
        return ""
    if name == "mphantom":
        return f"hide({_row(kids) or chr(34) * 2})"
    if name == "mi":
        return _identifier(_text(element), element.get("mathvariant"))
    if name == "mn":
        value = _text(element)
        return value if value.isdigit() else string(value)
    if name == "mo":
        return _operator(_text(element))
    if name == "mtext":
        value = "".join(element.itertext()).replace("\n", " ")
        return string(value) if value else ""
    if name == "ms":
        return string(
            element.get("lquote", '"')
            + _text(element)
            + element.get("rquote", '"')
        )
    if name == "mspace":
        return _space(element.get("width"))
    if name == "mfrac":
        numerator, denominator = [*kids, None, None][:2]
        if element.get("bevelled") == "true":
            return f"{_arg(numerator)} \\/ {_arg(denominator)}"
        return f"frac({_arg(numerator)}, {_arg(denominator)})"
    if name == "msqrt":
        return f"sqrt({_row(kids) or chr(34) * 2})"
    if name == "mroot":
        base, index = [*kids, None, None][:2]
        return f"root({_arg(index)}, {_arg(base)})"
    if name in ("msub", "msup", "msubsup"):
        base, first, second = [*kids, None, None, None][:3]
        if name == "msub":
            return f"attach({_arg(base)}, b: {_arg(first)})"
        if name == "msup":
            return f"attach({_arg(base)}, t: {_arg(first)})"
        return f"attach({_arg(base)}, b: {_arg(first)}, t: {_arg(second)})"
    if name in ("munder", "mover", "munderover"):
        return _under_over(name, element, kids)
    if name == "mmultiscripts":
        return _multiscripts(kids)
    if name == "mtable":
        rows = []
        for row in kids:
            cells = (
                _children(row)[1:]
                if _local(row) == "mlabeledtr"
                else _children(row)
            )
            if _local(row) in ("mtr", "mlabeledtr"):
                rows.append(", ".join(_arg(cell) for cell in cells) or '""')
        return f"mat(delim: #none, {'; '.join(rows)})" if rows else ""
    if name in ("mtr", "mlabeledtr", "mtd"):
        return _row(kids)
    return _row(kids)  # anything else: its content


def _identifier(value: str, variant: str | None) -> str:
    """<mi>: one letter in italics, a longer name upright.

    This is MathML's default.
    """
    if not value:
        return ""
    if len(value) == 1:
        code = value if value.isalpha() else _char(value)
        if variant == "normal" and value.isalpha():
            code = f"upright({code})"
    else:
        code = string(value)  # a quoted name is set upright
        if variant == "italic":
            code = f"italic({code})"
    if variant and "bold" in variant:
        code = f"bold({code})"
    return code


def _operator(value: str) -> str:
    """<mo>: a symbol keeps its spacing class.

    A word ("max", "lim") is an operator name.
    """
    value = "".join(ch for ch in value if ch not in _INVISIBLE)
    if not value:
        return ""
    if len(value) == 1:
        return _char(value)
    if value.isalpha():
        return f"op({string(value)})"
    return (
        " ".join(_char(ch) for ch in value)
        if len(value) <= 3
        else string(value)
    )


def _char(ch: str) -> str:
    """One character as Typst math source."""
    if ch in _BARE:
        return _BARE[ch]
    if ch.isascii():
        return ch if ch.isalnum() else ("\\" + ch if ch.strip() else "")
    category = unicodedata.category(ch)
    # letters, digits, symbols, punctuation: Typst reads them as
    # themselves
    if category[0] in "LNSP":
        return ch
    return string(ch) if category[0] != "C" else ""


def _space(width: str | None) -> str:
    match = re.fullmatch(r"\s*([\d.]+)\s*(em|ex|pt|px|mm|cm)?\s*", width or "")
    if not match:
        return "thin"
    amount = float(match.group(1)) * {
        "em": 1,
        "ex": 0.5,
        "pt": 0.1,
        "px": 0.075,
        "mm": 0.28,
        "cm": 2.8,
    }.get(match.group(2) or "em", 1)
    if amount <= 0:
        return ""
    return next(name for limit, name in _SPACES if amount >= limit)


def _under_over(
    name: str, element: etree._Element, kids: list[etree._Element]
) -> str:
    base, first, second = [*kids, None, None, None][:3]
    base_code = _arg(base)
    if name == "mover" and first is not None and _local(first) == "mo":
        mark = _text(first)
        if mark in _OVERLINES:
            return f"overline({base_code})"
        # Typst accents with one character; a longer mark is set over
        # the base instead
        if len(mark) == 1 and (
            element.get("accent") == "true" or mark in _ACCENTS
        ):
            return f"accent({base_code}, {string(mark)})"
    if (
        name == "munder"
        and first is not None
        and _local(first) == "mo"
        and _text(first) in _OVERLINES
    ):
        return f"underline({base_code})"
    if name == "munder":
        return f"attach(limits({base_code}), b: {_arg(first)})"
    if name == "mover":
        return f"attach(limits({base_code}), t: {_arg(first)})"
    return f"attach(limits({base_code}), b: {_arg(first)}, t: {_arg(second)})"


def _multiscripts(kids: list[etree._Element]) -> str:
    if not kids:
        return ""
    base, rest = kids[0], kids[1:]
    split = next(
        (i for i, kid in enumerate(rest) if _local(kid) == "mprescripts"),
        len(rest),
    )
    post, pre = rest[:split], rest[split + 1 :]
    scripts = []
    for prefix, items in (("", post), ("l", pre)):
        subs = [_node(kid) for kid in items[0::2] if _local(kid) != "none"]
        sups = [_node(kid) for kid in items[1::2] if _local(kid) != "none"]
        if any(subs):
            scripts.append(f"b{prefix}: {' '.join(s for s in subs if s)}")
        if any(sups):
            scripts.append(f"t{prefix}: {' '.join(s for s in sups if s)}")
    return (
        f"attach({_arg(base)}, {', '.join(scripts)})"
        if scripts
        else _arg(base)
    )


# -- spoken ------------------------------------------------------------

_SPOKEN_OPERATORS = {
    "=": "równa się",
    "+": "plus",
    "-": "minus",
    "−": "minus",  # noqa: RUF001
    "±": "plus minus",
    "×": "razy",  # noqa: RUF001
    "⋅": "razy",
    "·": "razy",
    "∙": "razy",
    "*": "razy",
    "/": "podzielić przez",
    "÷": "podzielić przez",
    ":": "podzielić przez",
    "<": "mniejsze niż",
    ">": "większe niż",
    "≤": "mniejsze lub równe",
    "≥": "większe lub równe",
    "≠": "różne od",
    "≈": "w przybliżeniu równe",
    "≡": "tożsamościowo równe",
    "∑": "suma",
    "∏": "iloczyn",
    "∫": "całka",
    "%": "procent",
    "∞": "nieskończoność",
    "→": "dąży do",
    "∈": "należy do",
    "∉": "nie należy do",
    "′": "prim",  # noqa: RUF001
    "…": "i tak dalej",
}
_LARGE = {"∑": "suma", "∏": "iloczyn", "∫": "całka"}


def spoken(math: etree._Element) -> str:
    """The formula read aloud in Polish, the alternative text."""
    return re.sub(r"\s+", " ", _say_row(_children(math))).strip()


def _say_row(children: list[etree._Element]) -> str:
    return " ".join(
        part for part in (_say(child) for child in children) if part
    )


def _say(element: etree._Element | None) -> str:
    if element is None:
        return ""
    name = _local(element)
    kids = _children(element)
    if name in ("mi", "mn", "mtext", "ms"):
        return _text(element)
    if name == "mo":
        value = "".join(ch for ch in _text(element) if ch not in _INVISIBLE)
        return _SPOKEN_OPERATORS.get(value, value)
    if name == "mspace" or name in (
        "annotation",
        "annotation-xml",
        "none",
        "mprescripts",
        "mphantom",
    ):
        return ""
    if name == "semantics":
        return _say(kids[0]) if kids else ""
    if name == "mfrac":
        numerator, denominator = [*kids, None, None][:2]
        return (
            f"ułamek: {_say(numerator)} przez {_say(denominator)}, "
            "koniec ułamka"
        )
    if name == "msqrt":
        return f"pierwiastek kwadratowy z {_say_row(kids)}, koniec pierwiastka"
    if name == "mroot":
        base, index = [*kids, None, None][:2]
        return (
            f"pierwiastek stopnia {_say(index)} z {_say(base)}, "
            "koniec pierwiastka"
        )
    if name in ("msub", "msup", "msubsup"):
        base, first, second = [*kids, None, None, None][:3]
        sub = first if name != "msup" else None
        sup = (
            first if name == "msup" else second if name == "msubsup" else None
        )
        text = _say(base)
        if sub is not None:
            text += f" indeks dolny {_say(sub)}"
        if sup is not None:
            power = _say(sup)
            text += {
                "2": " do kwadratu",
                "3": " do sześcianu",
                "prim": " prim",
            }.get(power, f" do potęgi {power}")
        return text
    if name in ("munder", "mover", "munderover"):
        base, first, second = [*kids, None, None, None][:3]
        under = first if name != "mover" else None
        over = (
            first
            if name == "mover"
            else second
            if name == "munderover"
            else None
        )
        base_text = _say(base)
        if (
            name == "mover"
            and over is not None
            and _local(over) == "mo"
            and (_text(over) in _OVERLINES or _text(over) in _ACCENTS)
        ):
            return (
                f"{base_text} z kreską"
                if _text(over) in _OVERLINES
                else f"{base_text} z akcentem"
            )
        large = (
            base is not None and _local(base) == "mo" and _text(base) in _LARGE
        )
        text = base_text
        if under is not None:
            text += f" od {_say(under)}" if large else f" po {_say(under)}"
        if over is not None:
            text += f" do {_say(over)}" if large else f" nad {_say(over)}"
        return text + (" z" if large else "")
    if name == "mtable":
        rows = []
        for number, row in enumerate(kids, start=1):
            rows.append(
                f"wiersz {number}: "
                + ", ".join(_say(cell) for cell in _children(row))
            )
        return "macierz, " + "; ".join(rows) + ", koniec macierzy"
    if name == "mfenced":
        opening = element.get("open", "(")
        closing = element.get("close", ")")
        return f"{opening}{_say_row(kids)}{closing}"
    return _say_row(kids)
