"""Tests for whoosh.mcp -- the MCP server's dependency-free search core.

These keep the ``whoosh-mcp`` console script and the "Whoosh as an MCP server
for AI agents" docs backed by working code. The MCP SDK itself is an optional
dependency, so the tests exercise ``SearchCore`` (which has no MCP dependency)
and assert that ``build_mcp_server`` fails cleanly with a helpful message when
the SDK is absent.
"""

import asyncio
import builtins
import os

import pytest

from whoosh.mcp import DEFAULT_EXTS, SAMPLE_DOCS, SearchCore, build_mcp_server, main


def test_sample_core_search_ranks_relevant_doc():
    core = SearchCore.build()
    hits = core.search("global interpreter lock")
    assert hits, "expected at least one hit"
    assert hits[0]["id"] == "py-gil"
    assert set(hits[0]) == {"id", "title", "score", "snippet"}
    assert hits[0]["score"] > 0


def test_sample_core_fetch_roundtrip_and_missing():
    core = SearchCore.build()
    doc = core.fetch("bm25")
    assert doc["title"] == "BM25 ranking"
    assert "BM25" in doc["text"]
    assert core.fetch("does-not-exist")["error"] == "not found"


def test_search_limit_is_respected():
    core = SearchCore.build()
    # A term common to every sample doc, capped to 2 results.
    hits = core.search("search OR index OR the", limit=2)
    assert len(hits) <= 2


def test_from_directory_indexes_real_files(tmp_path):
    (tmp_path / "gil.md").write_text(
        "# Thread notes\nThe GIL serializes bytecode in CPython.\n", encoding="utf-8"
    )
    (tmp_path / "ranking.txt").write_text(
        "idf and term frequency drive bm25 scoring.\n", encoding="utf-8"
    )
    (tmp_path / "ignore.log").write_text("not indexed\n", encoding="utf-8")

    core = SearchCore.from_directory(str(tmp_path))

    hits = core.search("bm25 scoring")
    assert hits[0]["id"] == "ranking.txt"
    # First non-empty line, stripped of markdown heading marks, becomes the title.
    assert core.fetch("gil.md")["title"] == "Thread notes"
    # The .log file was outside DEFAULT_EXTS and must not have been indexed.
    assert core.fetch("ignore.log")["error"] == "not found"


def test_from_directory_recurses_and_uses_relative_ids(tmp_path):
    sub = tmp_path / "topics"
    sub.mkdir()
    (sub / "mcp.rst").write_text(
        "Model Context Protocol tools for agents.\n", encoding="utf-8"
    )
    core = SearchCore.from_directory(str(tmp_path))
    assert core.fetch(os.path.join("topics", "mcp.rst"))["title"].startswith(
        "Model Context"
    )


def test_from_directory_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        SearchCore.from_directory(str(tmp_path))


def test_default_exts_are_text_like():
    assert ".md" in DEFAULT_EXTS and ".txt" in DEFAULT_EXTS and ".rst" in DEFAULT_EXTS


def test_sample_docs_have_required_fields():
    assert SAMPLE_DOCS
    for d in SAMPLE_DOCS:
        assert {"id", "title", "body"} <= set(d)


def _block_mcp_sdks(monkeypatch):
    """Make every MCP SDK (`mcp` *and* standalone `fastmcp`) unimportable."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mcp" or name.startswith(("mcp.", "fastmcp")):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_build_mcp_server_without_sdk_raises_helpful_error(monkeypatch):
    _block_mcp_sdks(monkeypatch)
    with pytest.raises(ModuleNotFoundError, match=r"whoosh3\[mcp\]"):
        build_mcp_server(SearchCore.build())


def test_build_mcp_server_falls_back_to_standalone_fastmcp(monkeypatch):
    # With the official `mcp` SDK absent but standalone `fastmcp` present,
    # build_mcp_server transparently uses fastmcp.FastMCP. Skipped where the
    # standalone package isn't installed.
    pytest.importorskip("fastmcp")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    server = build_mcp_server(SearchCore.build())
    assert server.name == "whoosh-search"


def test_main_missing_corpus_files_returns_error(tmp_path, capsys):
    rc = main([str(tmp_path)])
    assert rc == 2
    assert "No indexable files" in capsys.readouterr().err


def test_main_without_sdk_prints_clean_message_and_exits_1(monkeypatch, capsys):
    # When no MCP SDK is installed, `whoosh-mcp` should print a single
    # actionable line (no chained traceback) and exit 1.
    _block_mcp_sdks(monkeypatch)
    rc = main([])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.strip().startswith("whoosh-mcp:")
    assert 'pip install "whoosh3[mcp]"' in err
    assert "Traceback" not in err


def test_build_mcp_server_exposes_search_and_fetch_when_sdk_present():
    # Only runs where the optional 'mcp' SDK is installed; skipped otherwise.
    pytest.importorskip("mcp")

    server = build_mcp_server(SearchCore.build())
    assert server.name == "whoosh-search"
    tools = asyncio.new_event_loop().run_until_complete(server.list_tools())
    assert {t.name for t in tools} == {"search", "fetch"}
