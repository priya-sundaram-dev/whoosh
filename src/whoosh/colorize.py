"""Terminal color helpers for search match highlighting."""
from __future__ import annotations

import os
import sys


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
        out.append("\033[1;33m" + text[j : j + len(term)] + "\033[0m")
        i = j + len(term)
    return "".join(out)
