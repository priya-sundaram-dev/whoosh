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
