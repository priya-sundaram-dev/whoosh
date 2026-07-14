"""Tests for the ``whoosh`` command-line interface (whoosh.cli)."""
import os

import pytest

from whoosh import cli


@pytest.fixture()
def corpus(tmp_path):
    (tmp_path / "alpha.txt").write_text(
        "The quick brown fox jumps over the lazy dog.\n"
        "Full text search is delightful.\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.md").write_text(
        "# Notes\nWhoosh is a pure-Python search library.\n"
        "It supports indexing and ranked retrieval.\n",
        encoding="utf-8",
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "gamma.rst").write_text(
        "Ranked retrieval uses BM25 by default in Whoosh.\n",
        encoding="utf-8",
    )
    # A binary file that must be skipped.
    (tmp_path / "logo.bin").write_bytes(b"\x00\x01\x02binary\x00")
    return tmp_path


def run(argv):
    return cli.main([str(a) for a in argv])


def test_index_then_search(corpus, capsys):
    rc = run(["index", corpus])
    assert rc == 0
    out = capsys.readouterr().out
    assert "3 added" in out  # 3 text files, binary skipped
    assert os.path.isdir(corpus / cli.INDEX_DIRNAME)

    rc = run(["search", "search", corpus])
    assert rc == 0
    out = capsys.readouterr().out
    assert "match" in out.lower()
    # Both files mentioning "search" should surface.
    assert "alpha.txt" in out or "beta.md" in out


def test_search_no_matches_returns_1(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "zzzznottherezzz", corpus])
    assert rc == 1
    assert "No matches" in capsys.readouterr().out


def test_search_without_index_errors(tmp_path, capsys):
    rc = run(["search", "anything", tmp_path])
    assert rc == 2
    assert "no index" in capsys.readouterr().err.lower()


def test_index_missing_directory_errors(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"
    rc = run(["index", missing])
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err.lower()


def test_incremental_update_detects_changes(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    # Add a new file and re-index incrementally.
    (corpus / "delta.txt").write_text("A brand new document about pandas.\n",
                                       encoding="utf-8")
    rc = run(["index", corpus, "--update"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 added" in out
    assert "3 unchanged" in out

    rc = run(["search", "pandas", corpus])
    assert rc == 0
    assert "delta.txt" in capsys.readouterr().out


def test_ext_filter(corpus, capsys):
    rc = run(["index", corpus, "--ext", ".md"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 added" in out  # only beta.md


def test_html_highlight_formatter(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--html"])
    assert rc == 0
    assert "<mark" in capsys.readouterr().out.lower()


def test_resolve_exts_normalizes():
    assert cli._resolve_exts("md,.txt") == (".md", ".txt")
    assert cli._resolve_exts("") == cli.DEFAULT_EXTS
