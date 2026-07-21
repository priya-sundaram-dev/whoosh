"""Terminal color helpers for search match highlighting."""
from __future__ import annotations

import os
import sys

from whoosh.highlight import Formatter, get_text

#: ANSI escape sequences used to emphasise matched terms in a terminal.
ANSI_START = "\033[1;33m"  # bold yellow
ANSI_END = "\033[0m"


def resolve_color_mode(mode: str) -> bool:
    """Return True if ANSI color should be used.

    mode: auto | always | never
    """
    m = (mode or "auto").lower()
    if m == "always":
        return True
    if m == "never":
        return False
    # auto
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def highlight(text: str, term: str, *, enabled: bool) -> str:
    """Wrap case-insensitive occurrences of term in bold yellow."""
    if not enabled or not term:
        return text
    low = text.lower()
    t = term.lower()
    out: list[str] = []
    i = 0
    while True:
        j = low.find(t, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        out.append(ANSI_START + text[j : j + len(term)] + ANSI_END)
        i = j + len(term)
    return "".join(out)


class AnsiFormatter(Formatter):
    """Wrap matched terms in ANSI escape codes for terminal display.

    This is the color-terminal counterpart to
    :class:`whoosh.highlight.HtmlFormatter`: it plugs into the normal
    highlighting pipeline, so it emphasises the *actual* matched tokens
    (including stemmed or otherwise expanded matches) rather than a naive
    substring search.
    """

    def __init__(self, between="...", start=ANSI_START, end=ANSI_END):
        """
        :param between: the text to add between fragments.
        :param start: the ANSI escape sequence to emit before a matched term.
        :param end: the ANSI escape sequence to emit after a matched term.
        """
        self.between = between
        self.start = start
        self.end = end

    def format_token(self, text, token, replace=False):
        ttxt = get_text(text, token, replace)
        return f"{self.start}{ttxt}{self.end}"
