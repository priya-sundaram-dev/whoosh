"""Tests for the ``whoosh`` command-line interface (whoosh.cli)."""

import os
import time
import pytest

from whoosh import cli, index
from whoosh.fields import TEXT, Schema


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


@pytest.fixture()
def term_index(tmp_path):
    """Index on disk with known ``body`` term frequencies (apple x3,
    banana x2, cherry x1).

    Built directly with a plain TEXT field instead of via ``whoosh index``:
    the CLI schema stems ``body`` terms (StemmingAnalyzer turns "apple" into
    "appl"), so indexing through the CLI would make exact term assertions
    impossible. ``whoosh stats`` only needs the index on disk.
    """
    index_dir = tmp_path / cli.INDEX_DIRNAME
    index_dir.mkdir()
    ix = index.create_in(str(index_dir), Schema(body=TEXT))
    writer = ix.writer()
    writer.add_document(body="apple apple apple banana banana")
    writer.add_document(body="cherry")
    writer.commit()
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


def test_search_no_highlight_plain_output(corpus, capsys):
    """--no-highlight prints a plain body slice with no UPPERCASE markup."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--no-highlight"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "match" in out.lower()
    # The matched term is lowercased in the source, so no UPPERCASE marker.
    assert "WHOOSH" not in out
    assert "<mark" not in out.lower()
    # The plain leading slice should be present verbatim (lowercased term).
    assert "whoosh" in out.lower()


def test_search_no_highlight_conflicts_with_html(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--no-highlight", "--html"])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()


def test_search_no_highlight_conflicts_with_json(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--no-highlight", "--json"])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()


def test_search_snippet_chars_limits_length(corpus, capsys):
    """--snippet-chars N bounds the plain snippet length."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--no-highlight", "--snippet-chars", "20"])
    assert rc == 0
    out = capsys.readouterr().out
    # Each snippet line (indented) should be short; check the ellipsis marker
    # appears, indicating truncation happened.
    assert "..." in out
    for line in out.splitlines():
        if line.startswith("   "):  # snippet lines are indented
            # 20 chars + optional "..." + indent; keep a generous bound.
            assert len(line.strip()) <= 20 + len("...")


def test_search_snippet_chars_rejects_nonpositive(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--snippet-chars", "0"])
    err = capsys.readouterr().err
    assert "positive" in err.lower()


def test_resolve_exts_normalizes():
    assert cli._resolve_exts("md,.txt") == (".md", ".txt")
    assert cli._resolve_exts("") == cli.DEFAULT_EXTS


def test_search_json_output(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    import json
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "path" in data[0]
    assert "score" in data[0]
    assert "snippet" in data[0]


def test_search_mutually_exclusive_json_html(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--json", "--html"])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()



def test_search_limit_invalid(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "search", corpus, "--limit", "0"])
    err = capsys.readouterr().err
    assert "invalid positive int value" in err.lower()


def test_search_limit(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, "--limit", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("1.") == 1
    assert "2." not in out


def test_search_field_restricts_query(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    assert run(["search", "whoosh", corpus]) == 0
    assert "beta.md" in capsys.readouterr().out

    assert run(["search", "whoosh", corpus, "--field", "title"]) == 1
    assert "no matches" in capsys.readouterr().out.lower()

    assert run(["search", "whoosh", corpus, "--field", "body"]) == 0
    assert "beta.md" in capsys.readouterr().out

    assert run([
        "search", "whoosh", corpus,
        "--field", "title", "--field", "body",
    ]) == 0
    assert "beta.md" in capsys.readouterr().out


def test_search_field_invalid(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--field", "badfield"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown field" in err.lower()


def test_search_fields_invalid(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--fields", "badfield"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown field" in err.lower()


def test_search_fields_json(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--json", "--fields", "path"])
    assert rc == 0
    out = capsys.readouterr().out
    import json
    data = json.loads(out)
    assert len(data) > 0
    assert "path" in data[0]
    assert "score" not in data[0]
    assert "snippet" not in data[0]


def test_search_fields_text(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--fields", "path"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "path:" in out
    assert "score" not in out

def test_search_count(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, "--count"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "2"


def test_search_count_zero_matches(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "zzzznottherezzz", corpus, "--count"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "0"


def test_search_mutually_exclusive_count_json_html(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--count", "--json"])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()

    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, "--count", "--html"])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()


def test_search_summary_all_shown(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus])
    assert rc == 0
    out, err = capsys.readouterr()
    assert "2 matches." in err
    assert "Showing" not in err
    assert "matches for" in out
    assert "match." not in out

def test_search_summary_truncated(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, "--limit", "1"])
    assert rc == 0
    out, err = capsys.readouterr()
    assert "Showing 1 of 2 matches." in err
    assert "matches for" in out
    assert "Showing" not in out

def test_version_flag(capsys):
    from whoosh import __version_str__
    with pytest.raises(SystemExit) as excinfo:
        run(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "whoosh" in out.lower()
    assert __version_str__ in out


def test_version_flag_short(capsys):
    from whoosh import __version_str__
    with pytest.raises(SystemExit) as excinfo:
        run(["-V"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "whoosh" in out.lower()
    assert __version_str__ in out


def test_help_shows_project_url(capsys):
    """--help epilog and --version point users to the project home."""
    with pytest.raises(SystemExit):
        run(["--help"])
    help_out = capsys.readouterr().out
    assert "github.com/priya-sundaram-dev/whoosh" in help_out
    with pytest.raises(SystemExit):
        run(["--version"])
    ver_out = capsys.readouterr().out
    assert "github.com/priya-sundaram-dev/whoosh" in ver_out


def test_index_exclude(tmp_path, capsys):
    (tmp_path / "keep.txt").write_text("keep me")
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "skip.txt").write_text("skip me")
    (tmp_path / "vendor.min.js").write_text("vendor")

    rc = run(["index", tmp_path, "--exclude", "build/*", "--exclude", "*.min.js"])
    assert rc == 0

    # Check that keep.txt was indexed, but not the others
    capsys.readouterr()
    rc = run(["search", "keep", tmp_path])
    assert rc == 0
    assert "keep.txt" in capsys.readouterr().out

    rc = run(["search", "skip", tmp_path])
    assert rc == 1  # Should find no matches

    rc = run(["search", "vendor", tmp_path])
    assert rc == 1  # Should find no matches


def test_index_dry_run_lists_files_without_touching_index(tmp_path, capsys):
    """--dry-run lists the files that would be indexed and never creates
    the index, honoring --ext/--exclude filters."""
    (tmp_path / "keep.txt").write_text("keep me", encoding="utf-8")
    (tmp_path / "notes.md").write_text("some notes", encoding="utf-8")
    # A file whose extension is not indexed by default -> must not be listed.
    (tmp_path / "photo.png").write_bytes(b"\x89PNG not really text")
    # A file the exclude filter should drop -> must not be listed.
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "generated.txt").write_text("generated", encoding="utf-8")

    rc = run(["index", tmp_path, "--dry-run", "--exclude", "build/*"])
    assert rc == 0
    out, err = capsys.readouterr()

    # Matching, non-excluded files are listed (one relative path per line).
    assert "keep.txt" in out
    assert "notes.md" in out
    # Non-matching extension is excluded from the listing.
    assert "photo.png" not in out
    # Excluded path is excluded from the listing.
    assert "generated.txt" not in out
    assert os.path.join("build", "generated.txt") not in out
    # A short summary count is printed.
    assert "2 files" in err

    # A dry run must never create/clear/write the index.
    assert not os.path.isdir(tmp_path / cli.INDEX_DIRNAME)


def test_index_dry_run_leaves_existing_index_untouched(corpus, capsys):
    """--dry-run against an already-indexed directory must not clear or
    rewrite the existing .whoosh_index."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    index_dir = corpus / cli.INDEX_DIRNAME
    before = sorted(os.listdir(index_dir))

    rc = run(["index", corpus, "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha.txt" in out
    # The existing index files are untouched (not cleared or rewritten).
    assert sorted(os.listdir(index_dir)) == before


def test_stats_no_index_errors(tmp_path, capsys):
    rc = run(["stats", tmp_path])
    assert rc == 2
    assert "no index" in capsys.readouterr().err


def test_stats_text_output(corpus, capsys):
    run(["index", corpus])
    capsys.readouterr()
    rc = run(["stats", corpus])
    assert rc == 0
    out = capsys.readouterr().out
    assert "documents:" in out
    assert "fields:" in out
    # schema fields from build_schema()
    assert "path" in out and "body" in out
    assert "size on disk:" in out


def test_stats_json_output(corpus, capsys):
    import json as _json
    run(["index", corpus])
    capsys.readouterr()
    rc = run(["stats", corpus, "--json"])
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["doc_count"] >= 1
    assert payload["size_bytes"] > 0
    names = {f["name"] for f in payload["fields"]}
    assert {"path", "title", "body", "mtime"} <= names


def test_stats_top_terms_orders_by_frequency(term_index, capsys):
    rc = run(["stats", term_index, "--top-terms", "body", "--top", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Top terms in 'body':" in out
    # Frequencies print as ints, most-frequent-first.
    assert "  3  apple" in out
    assert "  2  banana" in out
    assert out.index("apple") < out.index("banana")
    # --top 2 drops cherry (frequency 1).
    assert "cherry" not in out


def test_stats_top_terms_unknown_field(term_index, capsys):
    rc = run(["stats", term_index, "--top-terms", "nosuchfield"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no field 'nosuchfield' in index" in err


def test_stats_top_terms_field_without_frequencies(corpus, capsys):
    """Field types without term frequencies (NUMERIC mtime): clean error."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["stats", corpus, "--top-terms", "mtime"])
    assert rc == 2
    err = capsys.readouterr().err
    # Clear, actionable message rather than a leaked low-level decode error.
    assert "does not store text terms" in err
    assert "mtime" in err
    assert "NUMERIC" in err
    assert "invalid literal" not in err  # no leaked int() error
    assert "Traceback" not in err


def test_human_bytes():
    assert cli._human_bytes(0) == "0 B"
    assert cli._human_bytes(512) == "512 B"
    assert cli._human_bytes(1536).endswith("KB")
    assert cli._human_bytes(5 * 1024 * 1024).endswith("MB")

def test_sort_by_mtime_orders_newest_first(tmp_path, capsys):
    (tmp_path / "old.txt").write_text("shared search term", encoding="utf-8")
    time.sleep(1.1)
    (tmp_path / "new.txt").write_text("shared search term", encoding="utf-8")
    assert run(["index", tmp_path]) == 0
    capsys.readouterr()

    rc = run(["search", "shared", tmp_path, "--sort-by", "mtime"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.index("new.txt") < out.index("old.txt")


def test_sort_by_default_is_score(tmp_path, capsys):
    (tmp_path / "old.txt").write_text("shared search term", encoding="utf-8")
    time.sleep(1.1)
    (tmp_path / "new.txt").write_text("shared search term", encoding="utf-8")
    assert run(["index", tmp_path]) == 0
    capsys.readouterr()

    rc = run(["search", "shared", tmp_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "new.txt" in out
    assert "old.txt" in out