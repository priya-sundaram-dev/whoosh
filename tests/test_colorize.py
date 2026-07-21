import os
from whoosh.colorize import highlight, resolve_color_mode


def test_resolve_color_modes(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert resolve_color_mode("always") is True
    assert resolve_color_mode("never") is False
    monkeypatch.setenv("NO_COLOR", "1")
    assert resolve_color_mode("auto") is False


def test_highlight_wraps_match():
    s = highlight("Hello World", "world", enabled=True)
    assert "\033[1;33m" in s
    assert "World" in s
    assert highlight("Hello", "x", enabled=False) == "Hello"
