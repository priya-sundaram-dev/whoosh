"""Guard tests for ``scripts/bump_version.py``.

The release helper only prevents red-on-release CI if its regexes keep matching
the real files. These tests make sure the script can still locate the version in
the package and both site pages, and that a round-trip bump leaves everything in
sync (and restores cleanly), so a future refactor of those files can't silently
break the release tooling.
"""

import importlib.util
import os

import pytest

import whoosh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
SCRIPT = os.path.join(ROOT, "scripts", "bump_version.py")


def _load():
    spec = importlib.util.spec_from_file_location("bump_version", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_reports_current_version():
    bump = _load()
    assert bump.current_version() == whoosh.__version_str__


def test_check_passes_for_current_state():
    bump = _load()
    assert bump.check() == 0


@pytest.mark.thread_unsafe(
    reason="mutates the real package/site files on disk during the bump"
)
def test_round_trip_bump_restores_files(tmp_path):
    bump = _load()
    originals = {
        p: open(p, encoding="utf-8").read()
        for p in (bump.INIT, bump.INDEX_HTML, bump.MAINTAINED_HTML)
    }
    current = bump.current_version()
    try:
        bump.set_version("9.9.9")
        assert bump.check("9.9.9") == 0
        assert bump.current_version() == "9.9.9"
    finally:
        bump.set_version(current)
    # byte-for-byte restoration
    for path, text in originals.items():
        assert open(path, encoding="utf-8").read() == text


def test_changelog_section_detection():
    bump = _load()
    # The current released version must already have a CHANGELOG heading.
    assert bump.changelog_has_section(bump.current_version())
    # A version that was never released must not.
    assert not bump.changelog_has_section("0.0.1")


def test_commit_refuses_without_changelog_section(tmp_path, monkeypatch, capsys):
    bump = _load()
    # A brand-new version that is in sync at the package level but has no
    # CHANGELOG section must be refused before any git call happens.
    import subprocess

    def _fail_if_called(*a, **k):  # pragma: no cover - must not run
        raise AssertionError("git should not be invoked when the guard trips")

    monkeypatch.setattr(subprocess, "run", _fail_if_called)
    # check() would fail for an unbumped version, so force it to pass and make
    # sure the CHANGELOG guard is what stops the commit.
    monkeypatch.setattr(bump, "check", lambda version=None: 0)
    assert bump.commit_release("0.0.1") == 1
    assert "no '## 0.0.1'" in capsys.readouterr().out
