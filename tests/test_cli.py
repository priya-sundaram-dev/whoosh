"""Tests for the ``whoosh`` command-line interface (whoosh.cli)."""

import argparse
import json
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


def test_color_always_emits_ansi(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--color", "always"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\033[1;33m" in out and "\033[0m" in out
    # ANSI mode should not also UPPERCASE the matched term.
    assert "WHOOSH" not in out


def test_color_never_has_no_ansi(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--color", "never"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\033[" not in out
    # Default text formatter still UPPERCASEs matches.
    assert "WHOOSH" in out


def test_color_auto_no_ansi_when_not_tty(corpus, capsys):
    # Under capsys stdout is not a TTY, so 'auto' must not colorize.
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--color", "auto"])
    assert rc == 0
    assert "\033[" not in capsys.readouterr().out


def test_color_highlights_stemmed_match(corpus, capsys):
    # Query "jumping" stems to match "jumps"; the Formatter-based colorizer
    # must wrap the actual matched token, not a naive substring.
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "jumping", corpus, "--color", "always"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\033[1;33mjumps\033[0m" in out


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


@pytest.mark.parametrize("raw,expected", [
    ("1024", 1024),
    ("500k", 500 * 1024),
    ("500K", 500 * 1024),
    ("10MB", 10 * 1024 * 1024),
    ("2g", 2 * 1024 ** 3),
    ("2Gb", 2 * 1024 ** 3),
])


def test_parse_size_valid(raw, expected):
    assert cli._parse_size(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "10XB", "-5", "5.5m", "10 MB!"])
def test_parse_size_invalid(raw):
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_size(raw)


def test_search_json_output(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "whoosh", corpus, "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "path" in data[0]
    assert "score" in data[0]
    assert "snippet" in data[0]


@pytest.mark.parametrize("flag", ["--jsonl", "--ndjson"])
def test_search_jsonl_output(corpus, capsys, flag):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, flag])
    assert rc == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    data = [json.loads(line) for line in lines]
    assert len(data) == 2
    assert not out.startswith("[")
    for hit in data:
        assert "path" in hit
        assert "score" in hit
        assert "snippet" in hit

    assert run(["search", "search", corpus, "--json"]) == 0
    assert data == json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("flag", ["--jsonl", "--ndjson"])
def test_search_jsonl_no_matches(corpus, capsys, flag):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "zzzznottherezzz", corpus, flag])
    assert rc == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


def test_search_json_no_matches_remains_array(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "zzzznottherezzz", corpus, "--json"])
    assert rc == 1
    assert capsys.readouterr().out == "[]\n"


@pytest.mark.parametrize("flag", ["--jsonl", "--ndjson"])
@pytest.mark.parametrize(
    "other", ["--json", "--html", "--no-highlight", "--count"])
def test_search_jsonl_is_mutually_exclusive(corpus, capsys, flag, other):
    with pytest.raises(SystemExit):
        run(["search", "whoosh", corpus, flag, other])
    err = capsys.readouterr().err
    assert "not allowed with argument" in err.lower()


def test_search_jsonl_fields_and_limit(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run([
        "search", "search", corpus, "--jsonl", "--fields", "path",
        "--limit", "1",
    ])
    assert rc == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert set(json.loads(lines[0])) == {"path"}


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


def test_search_pages_cover_the_same_hits_as_one_large_page(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    pages = []
    for page in (1, 2):
        assert run([
            "search", "search", corpus, "--json", "--fields", "path",
            "--limit", "1", "--page", str(page),
        ]) == 0
        pages.extend(json.loads(capsys.readouterr().out))

    assert run([
        "search", "search", corpus, "--json", "--fields", "path",
        "--limit", "2",
    ]) == 0
    all_at_once = json.loads(capsys.readouterr().out)
    assert pages == all_at_once


def test_search_page_footer_and_global_result_number(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    assert run(["search", "search", corpus, "--limit", "1", "--page", "2"]) == 0
    out, err = capsys.readouterr()
    assert "2." in out
    assert "Page 2/2 (2 total)." in err


def test_search_page_rejects_nonpositive_values(corpus, capsys):
    with pytest.raises(SystemExit):
        run(["search", "search", corpus, "--page", "0"])
    assert "invalid positive int value" in capsys.readouterr().err.lower()


def test_search_page_beyond_last_is_empty(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    assert run(["search", "search", corpus, "--limit", "1", "--page", "3"]) == 1
    assert "No matches" in capsys.readouterr().out

    assert run([
        "search", "search", corpus, "--json", "--limit", "1", "--page", "3",
    ]) == 1
    assert capsys.readouterr().out == "[]\n"


def test_search_count_ignores_page_and_reports_total(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    assert run(["search", "search", corpus, "--count", "--page", "2"]) == 0
    assert capsys.readouterr().out.strip() == "2"


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


def test_search_or_broadens_recall(corpus, capsys):
    # "fox" is only in alpha.txt; "search" is in alpha.txt and beta.md.
    # Default (AND) requires both terms -> only alpha.txt matches.
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "fox search", corpus, "--count"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1"

    # With --or, documents containing ANY term match -> both files.
    rc = run(["search", "fox search", corpus, "--or", "--count"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


def test_search_or_with_field(corpus, capsys):
    # --or must also apply when an explicit --field is selected.
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "fox search", corpus, "--field", "body",
              "--or", "--count"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "2"


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


def test_index_max_size_skips_large_files(tmp_path, capsys):
    (tmp_path / "small.txt").write_text("apple " * 20, encoding="utf-8")
    (tmp_path / "big.txt").write_text("apple " * 1000, encoding="utf-8")

    rc = run(["index", tmp_path, "--max-size", "1k"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 added" in out

    capsys.readouterr()
    rc = run(["search", "apple", tmp_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "small.txt" in out
    assert "big.txt" not in out


def test_index_max_size_dry_run_matches_real_run(tmp_path, capsys):
    (tmp_path / "small.txt").write_text("apple " * 20, encoding="utf-8")
    (tmp_path / "big.txt").write_text("apple " * 1000, encoding="utf-8")

    rc = run(["index", tmp_path, "--max-size", "1k", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "small.txt" in out
    assert "big.txt" not in out


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
    run(["index", corpus])
    capsys.readouterr()
    rc = run(["stats", corpus, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
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

    rc = run(["search", "shared", tmp_path, "--sort-by", "mtime", "--jsonl"])
    assert rc == 0
    paths = [
        hit["path"]
        for hit in map(json.loads, capsys.readouterr().out.splitlines())
    ]
    assert paths.index("new.txt") < paths.index("old.txt")


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


def test_search_files_with_matches_prints_paths(corpus, capsys):
    """-l prints one bare path per match, newline-separated, no scores/snippets."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, "-l"])
    assert rc == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == 2
    for line in lines:
        assert line.endswith(".txt") or line.endswith(".md") or line.endswith(".rst")
    assert "alpha.txt" in out
    assert "beta.md" in out


def test_search_files_with_matches_no_matches_returns_1(corpus, capsys):
    """-l with no matches -> empty stdout, exit 1."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "zzzznottherezzz", corpus, "-l"])
    assert rc == 1
    assert capsys.readouterr().out == ""


def test_search_files_with_matches_honors_limit_and_page(corpus, capsys):
    """-l respects --limit and --page."""
    assert run(["index", corpus]) == 0
    capsys.readouterr()
    rc = run(["search", "search", corpus, "-l", "--limit", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1

    # Second page should contain the second result.
    rc = run(["search", "search", corpus, "-l", "--limit", "1", "--page", "2"])
    assert rc == 0
    out2 = capsys.readouterr().out
    assert len(out2.splitlines()) == 1
    assert out != out2  # Different hit on second page


def test_search_files_with_matches_is_mutually_exclusive(corpus, capsys):
    """-l conflicts with other output modes."""
    for other in ("--html", "--no-highlight", "--json", "--jsonl", "--count"):
        with pytest.raises(SystemExit):
            run(["search", "search", corpus, "-l", other])
        err = capsys.readouterr().err
        assert "not allowed with argument" in err.lower()


@pytest.mark.parametrize("flag", ["-0", "--null"])
def test_search_null_separates_paths_with_trailing_nul(corpus, capsys, flag):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    assert run(["search", "search", corpus, "-l", flag]) == 0
    out, err = capsys.readouterr()
    assert out.endswith("\0")
    assert set(out.split("\0")[:-1]) == {"alpha.txt", "beta.md"}
    assert "\n" not in out
    assert err == ""


def test_search_null_requires_files_with_matches(corpus, capsys):
    assert run(["search", "search", corpus, "-0"]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "--null requires --files-with-matches" in err


def test_search_null_no_matches_and_out_of_range_are_silent(corpus, capsys):
    assert run(["index", corpus]) == 0
    capsys.readouterr()

    assert run(["search", "zzzznottherezzz", corpus, "-l", "-0"]) == 1
    assert capsys.readouterr() == ("", "")

    assert run([
        "search", "search", corpus, "-l", "-0", "--limit", "1",
        "--page", "3",
    ]) == 1
    assert capsys.readouterr() == ("", "")


def test_index_follow_symlinks_includes_symlinked_directories(tmp_path, capsys):
    """--follow-symlinks indexes files reachable only through a symlink.

    Creates a target directory outside the indexed root, then a symlink to
    it under the indexed root. Without --follow-symlinks the symlinked file
    is invisible to os.walk; with it, the file should be indexed.
    """
    # Target directory OUTSIDE the indexed root.
    target = tmp_path / ".." / "outside_content"
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "outside.txt").write_text("secret content behind symlink",
                                       encoding="utf-8")

    # Symlink inside the indexed root pointing outside -> ../outside_content/
    link = tmp_path / "link_to_outside"
    os.symlink(target, link, target_is_directory=True)

    # Index without --follow-symlinks -> symlinked dir skipped.
    rc = run(["index", tmp_path])
    assert rc == 0
    capsys.readouterr()

    rc = run(["search", "secret", tmp_path])
    assert rc == 1  # No matches

    # Now index WITH --follow-symlinks.
    rc = run(["index", tmp_path, "--follow-symlinks"])
    assert rc == 0
    capsys.readouterr()

    rc = run(["search", "secret", tmp_path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "outside.txt" in out


def test_index_follow_symlinks_dry_run_matches_real_run(tmp_path, capsys):
    """--dry-run with --follow-symlinks previews the same files."""
    target = tmp_path / ".." / "outside_content"
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    (target / "outside.txt").write_text("secret content behind symlink",
                                       encoding="utf-8")
    link = tmp_path / "link_to_outside"
    os.symlink(target, link, target_is_directory=True)

    # Dry run without follow-symlinks.
    rc = run(["index", tmp_path, "--dry-run"])
    assert rc == 0
    _, err = capsys.readouterr()
    assert "0 files" in err  # only the symlink dir, no real files found

    # Dry run with --follow-symlinks.
    rc = run(["index", tmp_path, "--follow-symlinks", "--dry-run"])
    assert rc == 0
    out, err = capsys.readouterr()
    assert "1 file" in err
    assert "outside.txt" in out
