"""Type-checker smoke fixture for Whoosh3's public API (gh#3).

This module is *not* run as a normal test. Instead, CI type-checks it with
``mypy`` (see the ``types`` job in ``.github/workflows/ci.yml``). It exercises
the annotated public entry points the way a downstream user would, so that if a
future change breaks or removes an annotation, the type checker fails loudly
here rather than silently degrading the editor/mypy experience for users.

Keep this snippet realistic and minimal: index creation, a schema built from
the field-type constructors, adding a document, and running a query through the
searching layer.
"""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING, Any

from whoosh import index
from whoosh.fields import DATETIME, ID, NUMERIC, TEXT, Schema
from whoosh.qparser import QueryParser

if TYPE_CHECKING:
    from whoosh.searching import Hit, Results
    from whoosh.writing import IndexWriter


def build_schema() -> Schema:
    # Field-type constructors are annotated, so kwargs type-check.
    return Schema(
        id=ID(stored=True, unique=True),
        title=TEXT(stored=True),
        views=NUMERIC(stored=True),
        created=DATETIME(stored=True),
    )


def run() -> list[str]:
    schema = build_schema()
    tmpdir = tempfile.mkdtemp()

    # index.create_in returns an Index; open/exists helpers are annotated too.
    ix = index.create_in(tmpdir, schema)
    assert index.exists_in(tmpdir)

    # ix.writer() is annotated to return an IndexWriter; add_document /
    # update_document / commit are annotated ``-> None`` on the public base
    # class, and the writer works as a context manager.
    writer: IndexWriter = ix.writer()
    writer.add_document(id="1", title="First document about search")
    writer.commit()

    with ix.writer() as w:
        w.add_document(id="2", title="Second document about indexing")
        w.update_document(id="2", title="Second document about indexing v2")

    titles: list[str] = []
    with ix.searcher() as searcher:
        parser = QueryParser("title", schema=ix.schema)
        query = parser.parse("search")
        results: Results = searcher.search(query, limit=10)

        # Results inspection helpers are annotated, so their return types
        # flow into user code and type-check here.
        empty: bool = results.is_empty()
        scored: int = results.scored_length()
        est: int = results.estimated_length()
        exact: bool = results.has_exact_length()
        assert not empty or scored == 0
        assert est >= 0 and exact in (True, False)

        if scored:
            top_score: float | None = results.score(0)
            top_docnum: int = results.docnum(0)
            top_fields: dict[str, Any] = results.fields(0)
            assert top_docnum >= 0
            assert top_score is None or top_score >= 0.0
            assert isinstance(top_fields, dict)

        for docnum, score in results.items():
            assert docnum >= 0
            assert score is None or score >= 0.0

        for hit in results:
            hit_obj: Hit = hit
            # Hit's dict-like accessors are annotated.
            keys: list[str] = hit_obj.keys()
            fields: dict[str, Any] = hit_obj.fields()
            assert set(keys) <= set(fields)
            titles.append(str(hit_obj["title"]))

        # Searcher's document-lookup helpers are annotated, so their return
        # types flow into user code and type-check here.
        total: int = searcher.doc_count()
        total_all: int = searcher.doc_count_all()
        assert total <= total_all

        one: dict[str, Any] | None = searcher.document(id="1")
        assert one is None or isinstance(one, dict)

        found_docnum: int | None = searcher.document_number(id="1")
        assert found_docnum is None or found_docnum >= 0

        for stored in searcher.documents():
            assert isinstance(stored, dict)
        for dn in searcher.document_numbers():
            assert dn >= 0
    return titles


if __name__ == "__main__":
    print(run())
