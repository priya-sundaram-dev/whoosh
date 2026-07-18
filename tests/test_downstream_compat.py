"""Downstream-compatibility smoke tests.

These tests protect the public API surface that real, widely-used downstream
projects rely on, so that a `pip install whoosh3` stays a genuine drop-in
replacement for the older ``Whoosh`` / ``Whoosh-Reloaded`` distributions.

The surface exercised here mirrors how `paperless-ngx
<https://github.com/paperless-ngx/paperless-ngx>`_ (a large document-management
project that depends on Whoosh for full-text search) uses the library: a mixed
``TEXT``/``KEYWORD``/``DATETIME``/``NUMERIC``/``BOOLEAN`` schema, an
``AsyncWriter``, ``MultifieldParser`` with the ``DateParserPlugin`` for date
range queries, ``TF_IDF`` scoring, and HTML highlighting.

If any of these break we want CI to be red before a release ships, because a
regression here means a painful migration for downstream users.
"""

import datetime
import tempfile

import pytest


def test_paperless_import_surface():
    """Every top-level import paperless-ngx performs must resolve."""
    from whoosh import classify, highlight, query  # noqa: F401
    from whoosh.fields import (  # noqa: F401
        BOOLEAN,
        DATETIME,
        KEYWORD,
        NUMERIC,
        TEXT,
        Schema,
    )
    from whoosh.highlight import HtmlFormatter  # noqa: F401
    from whoosh.idsets import BitSet, DocIdSet  # noqa: F401
    from whoosh.index import (  # noqa: F401
        FileIndex,
        LockError,
        create_in,
        exists_in,
        open_dir,
    )
    from whoosh.qparser import MultifieldParser, QueryParser  # noqa: F401
    from whoosh.qparser.dateparse import DateParserPlugin, English  # noqa: F401
    from whoosh.qparser.plugins import FieldsPlugin  # noqa: F401
    from whoosh.reading import IndexReader  # noqa: F401
    from whoosh.scoring import TF_IDF  # noqa: F401
    from whoosh.searching import ResultsPage, Searcher  # noqa: F401
    from whoosh.util.times import timespan  # noqa: F401
    from whoosh.writing import AsyncWriter  # noqa: F401


def _build_index(path):
    from whoosh.fields import BOOLEAN, DATETIME, KEYWORD, NUMERIC, TEXT, Schema
    from whoosh.index import create_in
    from whoosh.writing import AsyncWriter

    schema = Schema(
        id=NUMERIC(stored=True, unique=True),
        title=TEXT(stored=True),
        content=TEXT(),
        correspondent=TEXT(sortable=True),
        tag=KEYWORD(commas=True, scorable=True, lowercase=True),
        created=DATETIME(sortable=True),
        added=DATETIME(sortable=True),
        has_type=BOOLEAN(),
    )
    ix = create_in(path, schema)
    writer = AsyncWriter(ix)
    writer.add_document(
        id=1,
        title="Invoice March",
        content="electricity invoice for march",
        correspondent="Utility Co",
        tag="bills,utilities",
        created=datetime.datetime(2023, 3, 15),
        added=datetime.datetime(2023, 3, 16),
        has_type=True,
    )
    writer.add_document(
        id=2,
        title="Contract",
        content="annual service contract renewal",
        correspondent="Service Inc",
        tag="contracts",
        created=datetime.datetime(2024, 1, 5),
        added=datetime.datetime(2024, 1, 6),
        has_type=True,
    )
    writer.commit()
    return ix


def test_paperless_style_query_and_highlight():
    from whoosh import highlight
    from whoosh.highlight import HtmlFormatter
    from whoosh.qparser import MultifieldParser
    from whoosh.qparser.dateparse import DateParserPlugin
    from whoosh.scoring import TF_IDF

    path = tempfile.mkdtemp()
    ix = _build_index(path)

    with ix.searcher(weighting=TF_IDF()) as s:
        parser = MultifieldParser(
            ["content", "title", "correspondent"], ix.schema
        )
        parser.add_plugin(
            DateParserPlugin(basedate=datetime.datetime(2024, 6, 1))
        )

        # Plain term query.
        results = s.search(parser.parse("invoice"))
        assert [hit["id"] for hit in results] == [1]

        # ISO-8601 date-range query (regression-guarded parsing path).
        results = s.search(parser.parse("created:[2023-01-01 to 2023-12-31]"))
        assert [hit["id"] for hit in results] == [1]

        # HTML highlighting the way paperless renders match snippets: the text
        # is supplied explicitly because ``content`` is indexed but not stored.
        results = s.search(parser.parse("invoice"))
        results.fragmenter = highlight.ContextFragmenter()
        results.formatter = HtmlFormatter(
            tagname="span", classname="match", termclass="term"
        )
        snippet = results[0].highlights(
            "content", text="electricity invoice for march"
        )
        assert "span" in snippet


@pytest.mark.parametrize(
    "datestr",
    ["2023-05-17", "2023-05", "2023-05-17 14:30", "2023-05-17T14:30:00"],
)
def test_iso_date_parsing_for_search_apps(datestr):
    """ISO-8601 dates in query strings must parse (used by date-range search)."""
    from whoosh.qparser.dateparse import English

    parsed = English().date_from(datestr, datetime.datetime(2024, 6, 1))
    assert parsed is not None


def test_index_files_deletable_after_close(tmp_path):
    """Readers, searchers, and writers must release their file handles on
    close so the index directory can be deleted or an index file replaced.

    On POSIX this is almost always true (deletion of an open file succeeds),
    so this test is nearly a no-op there. It matters most on **Windows**,
    where an open file handle blocks ``os.remove``/``os.rename`` with
    ``PermissionError`` (WinError 32, "The process cannot access the file
    because it is being used by another process"). Downstreams such as
    paperless-ngx and MoinMoin rebuild/optimize indexes on Windows and hit
    exactly this path, so we guard the close-then-delete contract in CI.
    """
    import os
    import shutil

    from whoosh.fields import TEXT, Schema
    from whoosh.index import create_in, open_dir

    idx_dir = tmp_path / "ix"
    idx_dir.mkdir()

    schema = Schema(content=TEXT(stored=True))
    ix = create_in(str(idx_dir), schema)

    writer = ix.writer()
    writer.add_document(content="alpha beta gamma")
    writer.add_document(content="beta gamma delta")
    writer.commit()

    # Exercise the reader and searcher context-manager paths, which are the
    # documented way to guarantee handles are released.
    with ix.reader() as reader:
        assert reader.doc_count() == 2
    with ix.searcher() as searcher:
        from whoosh.qparser import QueryParser

        q = QueryParser("content", ix.schema).parse("beta")
        assert len(searcher.search(q)) == 2

    ix.close()

    # Every on-disk index file must now be removable. On Windows a leaked
    # handle would raise PermissionError here; on POSIX this simply confirms
    # the files exist and unlink cleanly.
    seg_files = [f for f in os.listdir(str(idx_dir))]
    assert seg_files, "expected the index to have written segment files"
    for name in seg_files:
        os.remove(os.path.join(str(idx_dir), name))

    # And the whole directory should tear down without EBUSY/PermissionError.
    shutil.rmtree(str(idx_dir))
    assert not idx_dir.exists()
